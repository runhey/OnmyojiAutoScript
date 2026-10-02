"""
Tests for ``oas.ext.proc.cmd``: the fast ``psutil.Process.cmdline()`` replacement.

``get_cmdline`` reads a command line straight out of psutil's C extension
instead of building a ``psutil.Process`` object first, which is what makes
``process_iter`` fast enough to sweep every pid on the machine. Its contract is
deliberately forgiving: every realistic failure -- the process is gone, access
is denied, the PEB is unreadable -- returns an empty list instead of raising,
because the callers are enumerating processes that are racing them to the exit.

The real-host tests spawn children whose argv is known exactly, so assertions
can be ``==`` rather than "contains". The error paths patch the module's
``cext`` handle, which is the only way to make psutil fail on demand.
"""

import os
import threading

import psutil
import pytest
from conftest import CallRecorder, stub_cext

import oas.ext.proc.cmd as cmd_module
from oas.ext.proc import get_cmdline, get_executable

# =============================================================================
# Helpers
# =============================================================================


#: argv tails that must survive a round trip through the PEB untouched.
ARGV_CASES = {
    'plain': [],
    'spaces': ['a b c'],
    'empty_string': [''],
    'unicode': ['\u4e2d\u6587 \u53c2\u6570'],
    'four_k_argument': ['x' * 4000],
    'double_quotes': ['he said "hi"'],
    'backslashes': [r'C:\a\b'],
    'trailing_backslash': ['C:\\dir\\'],
    'dashes': ['--name=x', '-v'],
    'duplicates': ['same', 'same'],
    'tab': ['a\tb'],
    'many_args': [f'arg{i}' for i in range(50)],
}

#: Exceptions ``get_cmdline`` promises to swallow into ``[]``.
CATCHABLE_ERRORS = [
    pytest.param(psutil.AccessDenied(1234), id='AccessDenied'),
    pytest.param(psutil.NoSuchProcess(1234), id='NoSuchProcess'),
    pytest.param(psutil.ZombieProcess(1234), id='ZombieProcess'),
    pytest.param(IndexError('empty cmdline'), id='IndexError'),
    pytest.param(OSError(87, 'wrong parameter'), id='OSError-WinError87'),
    pytest.param(OSError(13, 'permission denied'), id='OSError-EACCES'),
    pytest.param(ProcessLookupError(3, 'no such process'), id='ProcessLookupError'),
    pytest.param(RuntimeError('unexpected'), id='RuntimeError'),
    pytest.param(ValueError('unexpected'), id='ValueError'),
    pytest.param(KeyError('unexpected'), id='KeyError'),
]

#: pids that are out of range on every platform.
IMPOSSIBLE_PIDS = [2**31 - 1, 2**63 - 1, 999_999_999]
#: pids that are only "invalid" because Windows reserves them.
WINDOWS_RESERVED_PIDS = [0, 4]


@pytest.fixture
def cmd_cext(monkeypatch):
    """
    Replace the real ``cmd.cext`` handle with a recording stub.

    Returns:
        CallRecorder: set ``.result`` to control the value, ``.error`` to make
            every call raise, and inspect ``.calls`` to see how it was called.
    """
    recorder = CallRecorder(result=['/usr/bin/app'])
    monkeypatch.setattr(cmd_module, 'cext', stub_cext('cmd_cext', proc_cmdline=recorder))
    return recorder


# =============================================================================
# Real processes
# =============================================================================


class TestGetCmdlineOfSelf:
    """The reader must work on the process running the tests."""

    def test_returns_a_non_empty_list(self):
        assert isinstance(get_cmdline(os.getpid()), list)
        assert get_cmdline(os.getpid())

    def test_first_element_is_the_real_interpreter_image(self):
        """
        argv[0] is the image the OS started, which need not be sys.executable.

        Inside a virtualenv ``sys.executable`` is the ``.venv/Scripts/python.exe``
        shim, while the process image -- and therefore argv[0] -- is the base
        interpreter the shim launched. So this only checks that argv[0] is a
        Python binary; ``test_matches_psutil_process_cmdline`` is the exact one.
        """
        exe = get_cmdline(os.getpid())[0]
        assert os.path.isfile(exe)
        assert 'python' in os.path.basename(exe).lower()

    def test_matches_psutil_process_cmdline(self):
        """
        The fast path must agree with the slow path it replaces.

        ``oas.ext.proc`` exists to be a drop-in for ``psutil``'s cmdline, so a
        divergence here is the most important failure this suite can catch.
        """
        assert get_cmdline(os.getpid()) == psutil.Process(os.getpid()).cmdline()

    def test_contains_more_than_the_executable(self):
        """A pytest run has arguments, so the list has more than one element."""
        assert len(get_cmdline(os.getpid())) > 1


class TestGetCmdlineOfChildArgv:
    """A child's argv is reported back element for element."""

    @pytest.mark.parametrize('extra', list(ARGV_CASES.values()), ids=list(ARGV_CASES))
    def test_argv_round_trips_exactly(self, argv_child, extra):
        proc, argv = argv_child(extra=tuple(extra))
        assert get_cmdline(proc.pid) == argv

    def test_arg_count_is_preserved(self, argv_child):
        """Quoting must not merge or split arguments."""
        proc, argv = argv_child(extra=('a b', 'c', 'd e f', ''))
        assert len(get_cmdline(proc.pid)) == len(argv)

    def test_arg_order_is_preserved(self, argv_child):
        proc, argv = argv_child(extra=('first', 'second', 'third'))
        assert get_cmdline(proc.pid) == argv
        assert get_cmdline(proc.pid)[-3:] == ['first', 'second', 'third']

    def test_the_unique_token_is_visible(self, argv_child, unique_token):
        """The token that the iteration tests scan for is really in the argv."""
        proc, _ = argv_child()
        assert unique_token in get_cmdline(proc.pid)

    def test_a_second_child_is_read_independently(self, argv_child):
        """Two children differ only by their token, and both read correctly."""
        first, first_argv = argv_child(extra=('one',))
        second, second_argv = argv_child(extra=('two',))
        assert get_cmdline(first.pid) == first_argv
        assert get_cmdline(second.pid) == second_argv
        assert get_cmdline(first.pid) != get_cmdline(second.pid)

    def test_matches_psutil_for_a_child(self, argv_child):
        """The agreement with psutil holds for non-self processes too."""
        proc, _ = argv_child(extra=('x y',))
        assert get_cmdline(proc.pid) == psutil.Process(proc.pid).cmdline()


class TestGetCmdlineResultShape:
    """Return-value guarantees the docstring makes."""

    def test_elements_are_strings(self):
        assert all(isinstance(part, str) for part in get_cmdline(os.getpid()))

    def test_each_successful_call_returns_a_new_list(self, argv_child):
        """The caller may mutate the result without poisoning the next call."""
        proc, argv = argv_child()
        first = get_cmdline(proc.pid)
        first.append('mutated')
        assert get_cmdline(proc.pid) == argv

    def test_repeated_calls_are_equal(self):
        assert get_cmdline(os.getpid()) == get_cmdline(os.getpid())

    def test_each_error_returns_a_new_empty_list(self, cmd_cext):
        """``[]`` is built per call, so no shared mutable default leaks out."""
        cmd_cext.error = psutil.NoSuchProcess(1234)
        first = get_cmdline(1234)
        second = get_cmdline(1234)
        assert first == second == []
        assert first is not second


class TestGetCmdlineDeadProcess:
    """A process that already exited is the common case, not the exception."""

    def test_the_fixture_pid_really_is_dead(self, dead_pid):
        assert not psutil.pid_exists(dead_pid)

    def test_dead_pid_returns_empty_list(self, dead_pid):
        assert get_cmdline(dead_pid) == []

    def test_repeated_reads_stay_empty(self, dead_pid):
        assert get_cmdline(dead_pid) == get_cmdline(dead_pid) == []

    def test_reading_while_the_process_exits_never_raises(self, child_factory):
        """The pid is read throughout the exit race; only ``[]`` is allowed."""
        proc = child_factory()
        pid = proc.pid
        proc.kill()
        for _ in range(50):
            assert isinstance(get_cmdline(pid), list)
        proc.wait(timeout=10)

    def test_churn_of_spawning_and_killing_never_raises(self, child_factory):
        """Kill-and-read in a tight loop, which is the real call pattern."""
        for _ in range(15):
            proc = child_factory()
            pid = proc.pid
            assert get_cmdline(pid) != []
            proc.kill()
            proc.wait(timeout=10)
            assert get_cmdline(pid) == []


class TestGetCmdlineBoundaryPids:
    """Out-of-range pids are swallowed, never raised."""

    @pytest.mark.parametrize('pid', IMPOSSIBLE_PIDS)
    def test_impossible_pid_returns_empty(self, pid):
        assert get_cmdline(pid) == []

    @pytest.mark.parametrize('pid', [-1, -12345])
    def test_negative_pid_returns_empty(self, pid):
        assert get_cmdline(pid) == []

    @pytest.mark.skipif(not psutil.WINDOWS, reason='pid 0 and 4 are Windows-only placeholders')
    @pytest.mark.parametrize('pid', WINDOWS_RESERVED_PIDS)
    def test_windows_reserved_pid_returns_empty(self, pid):
        assert get_cmdline(pid) == []


class TestGetCmdlineConcurrency:
    """The reader holds no shared state, so threads may share it."""

    def test_concurrent_reads_of_distinct_children(self, child_factory):
        procs = [child_factory() for _ in range(8)]
        results = {}
        lock = threading.Lock()

        def read(proc):
            value = get_cmdline(proc.pid)
            with lock:
                results[proc.pid] = value

        threads = [threading.Thread(target=read, args=(proc,)) for proc in procs]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert set(results) == {proc.pid for proc in procs}
        assert all(value for value in results.values())

    def test_concurrent_reads_of_self_agree(self):
        """Hammering one pid from many threads gives one consistent answer."""
        expected = get_cmdline(os.getpid())
        results = []

        def read():
            results.append(get_cmdline(os.getpid()))

        threads = [threading.Thread(target=read) for _ in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert len(results) == 16
        assert all(value == expected for value in results)


# =============================================================================
# Error handling, with the C extension patched
# =============================================================================


class TestGetCmdlineErrorHandling:
    """Nothing a C extension can do may escape as an exception."""

    def test_success_path_returns_the_cext_result(self, cmd_cext):
        assert get_cmdline(1234) == ['/usr/bin/app']

    def test_empty_cext_result_passes_through(self, cmd_cext):
        cmd_cext.result = []
        assert get_cmdline(1234) == []

    def test_the_pid_is_forwarded_unchanged(self, cmd_cext):
        get_cmdline(4321)
        assert cmd_cext.last_call == ((4321,), {'use_peb': True})

    @pytest.mark.parametrize('error', CATCHABLE_ERRORS)
    def test_catchable_error_becomes_empty_list(self, cmd_cext, error):
        cmd_cext.error = error
        assert get_cmdline(1234) == []

    @pytest.mark.parametrize('error', [KeyboardInterrupt(), SystemExit(1)])
    def test_base_exception_propagates(self, cmd_cext, error):
        """
        Ctrl-C must not be swallowed.

        The module catches ``Exception`` broadly, and that is fine -- but
        ``BaseException`` is deliberately outside that net, because a bare
        ``except:`` here would make the CLI un-interruptible while it sweeps
        thousands of pids.
        """
        cmd_cext.error = error
        with pytest.raises(type(error)):
            get_cmdline(1234)

    def test_error_does_not_leak_into_the_next_call(self, cmd_cext):
        """One failure must not poison a later success."""
        cmd_cext.error = psutil.NoSuchProcess(1234)
        assert get_cmdline(1234) == []
        cmd_cext.error = None
        assert get_cmdline(1234) == ['/usr/bin/app']


# =============================================================================
# get_executable
# =============================================================================


class TestGetExecutable:
    """``get_executable`` is a thin, total wrapper over ``get_cmdline``."""

    def test_of_self_is_a_python_binary(self):
        exe = get_executable(os.getpid())
        assert os.path.isfile(exe)
        assert 'python' in os.path.basename(exe).lower()

    def test_of_self_equals_the_cmdline_head(self):
        assert get_executable(os.getpid()) == get_cmdline(os.getpid())[0]

    def test_of_child_equals_the_cmdline_head(self, argv_child):
        proc, argv = argv_child()
        assert get_executable(proc.pid) == argv[0]

    def test_returns_a_str(self):
        assert isinstance(get_executable(os.getpid()), str)

    def test_dead_pid_returns_empty_string(self, dead_pid):
        """Not ``None``: callers compare against ``''``."""
        result = get_executable(dead_pid)
        assert result == ''
        assert isinstance(result, str)

    @pytest.mark.parametrize('pid', IMPOSSIBLE_PIDS)
    def test_impossible_pid_returns_empty_string(self, pid):
        assert get_executable(pid) == ''

    def test_delegates_to_the_cmdline_head(self, cmd_cext):
        cmd_cext.result = ['/opt/tool', '--flag']
        assert get_executable(1234) == '/opt/tool'

    def test_empty_cmdline_returns_empty_string(self, cmd_cext):
        cmd_cext.result = []
        assert get_executable(1234) == ''

    @pytest.mark.parametrize('error', CATCHABLE_ERRORS)
    def test_never_raises_on_the_error_matrix(self, cmd_cext, error):
        cmd_cext.error = error
        assert get_executable(1234) == ''

    def test_reads_the_pid_only_once(self, cmd_cext):
        """One call to the C extension, not two."""
        get_executable(1234)
        assert cmd_cext.call_count == 1
