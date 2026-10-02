"""
Tests for ``oas.ext.proc.sig``: end a process without psutil's overhead.

Same ``(ok, exception)`` contract as ``nice``: the callers sweep a list of pids
and kill them, and a pid that exited a moment ago is routine, not an error. So
nothing is allowed to escape as a raised exception.

The platform semantics are worth pinning. On POSIX ``terminate`` sends SIGTERM
and ``kill`` sends SIGKILL, but on Windows *both* force-kill, because there is
no SIGTERM to be graceful with -- the two functions exist only so the caller's
code reads the same on both. The POSIX branch is exercised in
``test_platform_branches.py``; the tests here run against the real host.

The kill is deliberately not recursive: killing a parent leaves its children
running. ``test_killing_a_parent_leaves_its_child_alive`` pins that, because
"kill the emulator" callers depend on the emulator's own children being handled
by the emulator, not by a surprise process-tree sweep.
"""

import subprocess
import sys

import psutil
import pytest
from conftest import CallRecorder

import oas.ext.proc.sig as sig_module
from oas.ext.proc import process_kill, process_terminate

#: pids that no platform can resolve to a real process.
IMPOSSIBLE_PIDS = [2**31 - 1, 999_999_999]

SIG_FUNCTIONS = [
    pytest.param(process_terminate, 'terminate', id='terminate'),
    pytest.param(process_kill, 'kill', id='kill'),
]


# =============================================================================
# Real termination
# =============================================================================


class TestTerminateRealProcess:
    """The target really dies, and the caller is told so."""

    @pytest.mark.parametrize('func, _backend', SIG_FUNCTIONS)
    def test_reports_success_on_a_live_child(self, child_factory, func, _backend):
        child = child_factory()
        ok, err = func(child.pid)
        assert (ok, err) == (True, None)
        child.wait(timeout=15)

    @pytest.mark.parametrize('func, _backend', SIG_FUNCTIONS)
    def test_the_child_actually_exits(self, child_factory, func, _backend):
        child = child_factory()
        func(child.pid)
        assert child.wait(timeout=15) is not None
        assert child.poll() is not None

    @pytest.mark.parametrize('func, _backend', SIG_FUNCTIONS)
    def test_the_pid_is_gone_afterwards(self, child_factory, func, _backend):
        child = child_factory()
        pid = child.pid
        func(pid)
        child.wait(timeout=15)
        assert not psutil.pid_exists(pid)

    @pytest.mark.parametrize('func, _backend', SIG_FUNCTIONS)
    def test_a_child_is_alive_before_being_killed(self, child_factory, func, _backend):
        """Guards against the test passing because the child never started."""
        child = child_factory()
        assert psutil.pid_exists(child.pid)
        assert child.poll() is None
        func(child.pid)
        child.wait(timeout=15)

    def test_killing_many_children_all_report_success(self, child_factory):
        children = [child_factory() for _ in range(6)]
        results = [process_kill(child.pid) for child in children]
        assert results == [(True, None)] * 6
        for child in children:
            child.wait(timeout=15)
            assert not psutil.pid_exists(child.pid)

    def test_a_mix_of_terminate_and_kill_on_the_same_batch(self, child_factory):
        """Interleaving the two entry points must not interfere."""
        children = [child_factory() for _ in range(4)]
        results = []
        for index, child in enumerate(children):
            results.append(
                process_terminate(child.pid) if index % 2 else process_kill(child.pid)
            )
        assert all(ok for ok, _ in results)
        for child in children:
            child.wait(timeout=15)
            assert not psutil.pid_exists(child.pid)

    def test_killing_a_parent_leaves_its_child_alive(self, poll_until):
        """
        The kill is not recursive.

        ``process_kill`` is a single ``kill(2)``/``TerminateProcess``, so a
        grandchild is re-parented rather than swept up. Callers that want a tree
        gone must walk it themselves.
        """
        code = (
            'import subprocess, sys, time\n'
            'subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])\n'
            'time.sleep(60)\n'
        )
        parent = subprocess.Popen([sys.executable, '-c', code])
        grandchild = None
        try:
            assert poll_until(
                lambda: bool(psutil.Process(parent.pid).children()), timeout=20
            ), 'the grandchild never appeared'
            grandchild = psutil.Process(parent.pid).children()[0]

            assert process_kill(parent.pid) == (True, None)
            parent.wait(timeout=15)

            assert psutil.pid_exists(grandchild.pid), 'the grandchild was killed too'
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=15)
            if grandchild is not None:
                try:
                    grandchild.kill()
                except psutil.Error:
                    pass


# =============================================================================
# Failure paths
# =============================================================================


class TestTerminateFailurePaths:
    """A target that cannot be killed is reported, never raised."""

    @pytest.mark.parametrize('func, _backend', SIG_FUNCTIONS)
    def test_dead_pid(self, dead_pid, func, _backend):
        ok, err = func(dead_pid)
        assert ok is False
        assert isinstance(err, Exception)

    @pytest.mark.parametrize('func, _backend', SIG_FUNCTIONS)
    @pytest.mark.parametrize('pid', IMPOSSIBLE_PIDS)
    def test_impossible_pid(self, func, _backend, pid):
        ok, err = func(pid)
        assert ok is False
        assert isinstance(err, Exception)

    @pytest.mark.parametrize('func, _backend', SIG_FUNCTIONS)
    @pytest.mark.parametrize('pid', [0, -1])
    def test_self_harmful_pid_is_refused(self, func, _backend, pid):
        """
        pid 0 would hit the caller's whole process group on POSIX, and a
        negative pid names a group outright. Neither may ever succeed.
        """
        ok, err = func(pid)
        assert ok is False
        assert isinstance(err, Exception)

    @pytest.mark.parametrize('func, _backend', SIG_FUNCTIONS)
    def test_killing_the_same_pid_twice_fails_the_second_time(
        self, child_factory, func, _backend
    ):
        child = child_factory()
        assert func(child.pid) == (True, None)
        child.wait(timeout=15)
        ok, err = func(child.pid)
        assert ok is False
        assert isinstance(err, Exception)

    @pytest.mark.parametrize('func, _backend', SIG_FUNCTIONS)
    def test_killing_an_already_exited_process_fails(self, child_factory, func, _backend):
        """A child that exited on its own is not killable."""
        child = child_factory(
            [sys.executable, '-c', 'pass']
        )
        child.wait(timeout=15)
        ok, err = func(child.pid)
        assert ok is False
        assert isinstance(err, Exception)

    def test_a_refused_kill_does_not_disturb_this_process(self):
        """Trying to kill something else must leave the caller healthy."""
        assert process_kill(2**31 - 1)[0] is False
        assert psutil.pid_exists(psutil.Process().pid)


# =============================================================================
# Delegation to the backend, with it patched
# =============================================================================


class TestSigBackendDelegation:
    """The public wrappers are thin: one backend call, exact arguments."""

    @pytest.fixture
    def sig_backend(self, monkeypatch):
        """
        Replace the module's platform backend callables with recorders.

        Returns:
            dict: ``{'terminate': CallRecorder, 'kill': CallRecorder}``
        """
        recorders = {'terminate': CallRecorder(), 'kill': CallRecorder()}
        monkeypatch.setattr(sig_module, 'terminate', recorders['terminate'])
        monkeypatch.setattr(sig_module, 'kill', recorders['kill'])
        return recorders

    @pytest.mark.parametrize('func, backend', SIG_FUNCTIONS)
    def test_calls_the_backend_once_with_the_pid(self, sig_backend, func, backend):
        assert func(4321) == (True, None)
        assert sig_backend[backend].calls == [((4321,), {})]

    @pytest.mark.parametrize('func, backend', SIG_FUNCTIONS)
    def test_the_other_backend_is_not_touched(self, sig_backend, func, backend):
        func(4321)
        other = 'kill' if backend == 'terminate' else 'terminate'
        assert sig_backend[other].call_count == 0

    def test_terminate_and_kill_use_different_backends(self, sig_backend):
        process_terminate(1)
        process_kill(1)
        assert sig_backend['terminate'].call_count == 1
        assert sig_backend['kill'].call_count == 1

    @pytest.mark.parametrize('func, backend', SIG_FUNCTIONS)
    @pytest.mark.parametrize(
        'error',
        [
            pytest.param(PermissionError(13, 'denied'), id='PermissionError'),
            pytest.param(psutil.AccessDenied(1234), id='AccessDenied'),
            pytest.param(ProcessLookupError(3, 'gone'), id='ProcessLookupError'),
            pytest.param(OSError(13, 'denied'), id='OSError'),
            pytest.param(RuntimeError('unexpected'), id='RuntimeError'),
        ],
    )
    def test_backend_exception_is_returned_verbatim(
        self, sig_backend, func, backend, error
    ):
        sig_backend[backend].error = error
        ok, err = func(1234)
        assert ok is False
        assert err is error

    @pytest.mark.parametrize('func, backend', SIG_FUNCTIONS)
    @pytest.mark.parametrize('error', [KeyboardInterrupt(), SystemExit(1)])
    def test_base_exception_propagates(self, sig_backend, func, backend, error):
        sig_backend[backend].error = error
        with pytest.raises(type(error)):
            func(1234)

    @pytest.mark.parametrize('func, backend', SIG_FUNCTIONS)
    def test_success_after_a_failure_is_not_poisoned(self, sig_backend, func, backend):
        sig_backend[backend].error = ProcessLookupError(3, 'gone')
        assert func(1234) == (False, sig_backend[backend].error)
        sig_backend[backend].error = None
        assert func(1234) == (True, None)
