"""
Tests for ``oas.ext.proc.nice``: lower a process's priority the fast way.

Both entry points return ``(ok, exception)`` instead of raising, because the
callers use them opportunistically. Lowering the priority of an emulator you did
not start is expected to fail with ``PermissionError``, and that is not an error
for the caller -- it only means "carry on at normal priority". So the contract
under test is: *never raise*, report the failure in the tuple, and name the
exception so the caller can tell "denied" from "already gone".

Priority is restored after every single test by an autouse fixture. Without it
the rest of the suite would keep running at IDLE, which turns a passing suite
into a mysteriously slow one.
"""

import os
import sys

import psutil
import pytest
from conftest import CallRecorder

import oas.ext.proc.nice as nice_module
from oas.ext.proc import set_lower_process_priority, set_lowest_process_priority
from oas.ext.proc.nice import nice_get, nice_set

#: pid -> the exception psutil raises for it, probed on this host.
IMPOSSIBLE_PIDS = [2**31 - 1, 999_999_999]
RESERVED_PIDS = [0, 4]

PRIORITY_SETTERS = [
    pytest.param(set_lower_process_priority, id='lower'),
    pytest.param(set_lowest_process_priority, id='lowest'),
]


@pytest.fixture(autouse=True)
def restore_normal_priority():
    """
    Put the pytest process back to NORMAL after every test in this module.

    ``sys.platform`` is used rather than ``psutil.WINDOWS`` because several
    tests monkeypatch the latter to exercise the Unix branch.

    The restore is deliberately *not* wrapped in a try/except: raising your own
    process back to NORMAL always succeeds, and a silent failure here would turn
    a passing suite into a mysteriously slow one. If it ever breaks, it should
    break loudly.
    """
    yield
    value = psutil.NORMAL_PRIORITY_CLASS if sys.platform == 'win32' else 0
    psutil.Process().nice(value)


@pytest.fixture
def nice_recorder(monkeypatch):
    """
    Replace ``nice_set`` with a recorder.

    Returns:
        CallRecorder: ``.calls`` holds every ``(pid, nice)`` pair that the
            public functions tried to apply.
    """
    recorder = CallRecorder()
    monkeypatch.setattr(nice_module, 'nice_set', recorder)
    return recorder


# =============================================================================
# The tuple contract
# =============================================================================


class TestPriorityReturnContract:
    """``(ok, exception)`` -- never an exception on the way out."""

    @pytest.mark.parametrize('setter', PRIORITY_SETTERS)
    def test_returns_a_two_tuple(self, setter):
        result = setter()
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.parametrize('setter', PRIORITY_SETTERS)
    def test_flag_is_really_a_bool(self, setter):
        """``ok`` is compared with ``is`` by the callers, so no truthy extras."""
        ok, _ = setter()
        assert ok is True or ok is False

    @pytest.mark.parametrize('setter', PRIORITY_SETTERS)
    def test_success_implies_no_exception(self, setter):
        ok, err = setter()
        if ok:
            assert err is None

    @pytest.mark.parametrize('setter', PRIORITY_SETTERS)
    def test_failure_implies_an_exception(self, setter):
        ok, err = setter(pid=2**31 - 1)
        assert ok is False
        assert isinstance(err, Exception)

    def test_default_pid_targets_this_process(self, nice_recorder):
        set_lower_process_priority()
        assert nice_recorder.last_call[0][0] == os.getpid()

    def test_an_explicit_pid_is_used_verbatim(self, nice_recorder):
        set_lower_process_priority(4321)
        assert nice_recorder.last_call[0][0] == 4321

    def test_pid_zero_is_not_treated_as_default(self, nice_recorder):
        """``0`` and ``None`` must not be conflated."""
        set_lower_process_priority(0)
        assert nice_recorder.last_call[0][0] == 0


# =============================================================================
# The priority value that is applied
# =============================================================================


class TestPriorityValueMapping:
    """Windows uses priority classes; everything else uses nice values."""

    @pytest.mark.skipif(not psutil.WINDOWS, reason='Windows priority classes')
    def test_lower_uses_below_normal_on_windows(self, nice_recorder):
        set_lower_process_priority(5)
        assert nice_recorder.last_call == ((5, psutil.BELOW_NORMAL_PRIORITY_CLASS), {})

    @pytest.mark.skipif(not psutil.WINDOWS, reason='Windows priority classes')
    def test_lowest_uses_idle_on_windows(self, nice_recorder):
        set_lowest_process_priority(5)
        assert nice_recorder.last_call == ((5, psutil.IDLE_PRIORITY_CLASS), {})

    def test_lower_uses_nice_ten_on_unix(self, nice_recorder, monkeypatch):
        """The Unix branch is selected at call time, so it can be forced."""
        monkeypatch.setattr(psutil, 'WINDOWS', False)
        set_lower_process_priority(5)
        assert nice_recorder.last_call == ((5, 10), {})

    def test_lowest_uses_nice_nineteen_on_unix(self, nice_recorder, monkeypatch):
        monkeypatch.setattr(psutil, 'WINDOWS', False)
        set_lowest_process_priority(5)
        assert nice_recorder.last_call == ((5, 19), {})

    @pytest.mark.skipif(not psutil.WINDOWS, reason='Windows priority classes')
    def test_idle_is_lower_than_below_normal(self):
        """'lowest' must really be lower than 'lower'."""
        assert psutil.IDLE_PRIORITY_CLASS < psutil.BELOW_NORMAL_PRIORITY_CLASS

    def test_each_setter_calls_the_backend_exactly_once(self, nice_recorder):
        set_lower_process_priority(1)
        set_lowest_process_priority(1)
        assert nice_recorder.call_count == 2

    def test_the_two_setters_apply_different_values(self, nice_recorder):
        set_lower_process_priority(1)
        set_lowest_process_priority(1)
        lower_value = nice_recorder.calls[0][0][1]
        lowest_value = nice_recorder.calls[1][0][1]
        assert lower_value != lowest_value


# =============================================================================
# Real effect on this host
# =============================================================================


class TestPriorityRealEffect:
    """The value must actually reach the OS, not just the backend call."""

    def test_priority_starts_at_normal(self):
        """Proves the autouse restore fixture is doing its job."""
        expected = psutil.NORMAL_PRIORITY_CLASS if psutil.WINDOWS else 0
        assert psutil.Process().nice() == expected

    def test_nice_get_reads_the_current_priority(self):
        assert nice_get(os.getpid()) == psutil.Process().nice()

    def test_lower_really_changes_the_priority(self):
        ok, err = set_lower_process_priority()
        assert (ok, err) == (True, None)
        expected = psutil.BELOW_NORMAL_PRIORITY_CLASS if psutil.WINDOWS else 10
        assert psutil.Process().nice() == expected

    def test_lowest_really_changes_the_priority(self):
        ok, err = set_lowest_process_priority()
        assert (ok, err) == (True, None)
        expected = psutil.IDLE_PRIORITY_CLASS if psutil.WINDOWS else 19
        assert psutil.Process().nice() == expected

    def test_lowest_is_lower_than_lower_on_this_host(self):
        set_lower_process_priority()
        after_lower = psutil.Process().nice()
        set_lowest_process_priority()
        after_lowest = psutil.Process().nice()
        assert after_lowest < after_lower

    def test_applying_twice_is_idempotent(self):
        assert set_lowest_process_priority() == (True, None)
        assert set_lowest_process_priority() == (True, None)

    def test_a_child_priority_can_be_lowered_and_read_back(self, child_factory):
        """The other-process path, which is what the emulator callers use."""
        child = child_factory()
        ok, err = set_lowest_process_priority(child.pid)
        assert (ok, err) == (True, None)
        expected = psutil.IDLE_PRIORITY_CLASS if psutil.WINDOWS else 19
        assert psutil.Process(child.pid).nice() == expected

    def test_nice_get_raises_on_a_dead_process(self, dead_pid):
        """
        The raw accessor is *not* wrapped -- only the setters are.

        Note the exception type: psutil's C layer raises a *builtin*
        ``ProcessLookupError`` here, not ``psutil.NoSuchProcess``. That is
        precisely why ``cmd.get_cmdline`` broadens its catch to ``OSError`` and
        then adds a bare ``except Exception`` on top.
        """
        with pytest.raises(OSError):
            nice_get(dead_pid)

    def test_nice_set_raises_on_a_dead_process(self, dead_pid):
        """Same for the raw setter, which the public wrappers then catch."""
        value = psutil.IDLE_PRIORITY_CLASS if psutil.WINDOWS else 19
        with pytest.raises(OSError):
            nice_set(dead_pid, value)


# =============================================================================
# Failure paths
# =============================================================================


class TestPriorityFailurePaths:
    """Every failure arrives as ``(False, exception)``, never as a raise."""

    def test_dead_pid(self, dead_pid):
        ok, err = set_lowest_process_priority(dead_pid)
        assert ok is False
        assert isinstance(err, Exception)

    @pytest.mark.parametrize('pid', IMPOSSIBLE_PIDS)
    def test_impossible_pid(self, pid):
        ok, err = set_lower_process_priority(pid)
        assert ok is False
        assert isinstance(err, Exception)

    @pytest.mark.parametrize('pid', RESERVED_PIDS)
    def test_reserved_pid(self, pid):
        """pid 0 and 4 cannot be touched without elevation."""
        ok, err = set_lower_process_priority(pid)
        assert ok is False
        assert isinstance(err, Exception)

    def test_a_pid_too_large_for_a_c_long(self):
        """An overflow in the C layer is just another failure."""
        ok, err = set_lower_process_priority(2**63 - 1)
        assert ok is False
        assert isinstance(err, Exception)

    def test_failure_leaves_the_priority_untouched(self):
        """An impossible pid must not disturb this process."""
        before = psutil.Process().nice()
        set_lowest_process_priority(2**31 - 1)
        assert psutil.Process().nice() == before

    @pytest.mark.parametrize(
        'error',
        [
            pytest.param(PermissionError(13, 'denied'), id='PermissionError'),
            pytest.param(psutil.AccessDenied(1234), id='AccessDenied'),
            pytest.param(OSError(13, 'denied'), id='OSError'),
            pytest.param(psutil.NoSuchProcess(1234), id='NoSuchProcess'),
            pytest.param(RuntimeError('unexpected'), id='RuntimeError'),
        ],
    )
    def test_backend_exception_is_returned_verbatim(self, nice_recorder, error):
        """The caller needs the original exception, not a copy or a wrapper."""
        nice_recorder.error = error
        ok, err = set_lower_process_priority(1234)
        assert ok is False
        assert err is error

    @pytest.mark.parametrize('error', [KeyboardInterrupt(), SystemExit(1)])
    def test_base_exception_propagates(self, nice_recorder, error):
        """Ctrl-C must interrupt a long emulator sweep."""
        nice_recorder.error = error
        with pytest.raises(type(error)):
            set_lowest_process_priority(1234)
