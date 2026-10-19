import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.exception import TaskEnd
from tasks.AutoCheckinBigGod.script_task import ScriptTask


def task_with_process():
    task = object.__new__(ScriptTask)
    task._frida_session = subprocess.Popen(
        [sys.executable, '-c', 'import time; time.sleep(60)'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    task._frida_attached_pid = 123
    task.frida_pid = 123
    return task


@pytest.mark.parametrize('exit_kind', ['return', 'task_end', 'error', 'interrupt'])
def test_run_reaps_owned_process_on_every_exit(exit_kind):
    task = task_with_process()
    proc = task._frida_session
    commands = []
    task._adb_shell = lambda command: commands.append(command)
    task.device = SimpleNamespace(app_start=Mock())
    task.session = SimpleNamespace(close=Mock())

    def checkin():
        assert proc.poll() is None  # The process remains usable during the task.
        task._adb_connected = True
        task._restore_game_after_checkin = True
        if exit_kind == 'task_end':
            raise TaskEnd('AutoCheckinBigGod')
        if exit_kind == 'error':
            raise RuntimeError('failed')
        if exit_kind == 'interrupt':
            raise KeyboardInterrupt()

    task._run_checkin = checkin
    try:
        if exit_kind == 'return':
            task.run()
        else:
            expected = {'task_end': TaskEnd, 'error': RuntimeError, 'interrupt': KeyboardInterrupt}[exit_kind]
            with pytest.raises(expected):
                task.run()
        assert proc.poll() is not None
        assert all(pipe.closed for pipe in (proc.stdin, proc.stdout, proc.stderr))
        assert task._frida_session is None and task._frida_attached_pid is None
        assert task.frida_pid is None
        assert ['su -c "killall frida-server"'] in commands
        task.device.app_start.assert_called_once()
        task.session.close.assert_called_once()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)


def test_failed_adb_check_does_not_touch_unspecified_device():
    task = object.__new__(ScriptTask)
    task._run_checkin = Mock(side_effect=TaskEnd('AutoCheckinBigGod'))
    task._adb_shell = Mock()
    with pytest.raises(TaskEnd):
        task.run()
    task._adb_shell.assert_not_called()


def test_stdin_failure_reaps_repl_before_fallback():
    task = object.__new__(ScriptTask)
    proc = Mock()
    proc.poll.return_value = None
    proc.stdin.write.side_effect = BrokenPipeError()
    task._frida_session = proc
    task._frida_attached_pid = 123
    def fallback(*args):
        proc.wait.assert_called_once()
        assert task._frida_session is None
        return 'fallback'
    task._run_frida_script_oneshot = fallback
    assert task._run_frida_script(123, 'test') == 'fallback'
    proc.terminate.assert_called_once()


@pytest.mark.parametrize('error', [OSError('failed'), subprocess.TimeoutExpired('frida', 10)])
def test_oneshot_exception_reaps_process(monkeypatch, error):
    task = object.__new__(ScriptTask)
    task._get_frida_exe = lambda: 'frida'
    proc = Mock()
    proc.poll.return_value = None
    proc.communicate.side_effect = error
    monkeypatch.setattr('tasks.AutoCheckinBigGod.script_task.subprocess.Popen', lambda *a, **kw: proc)
    monkeypatch.setattr('tasks.AutoCheckinBigGod.script_task.time.sleep', lambda seconds: None)
    assert task._run_frida_script_oneshot(123, 'test') is None
    proc.terminate.assert_called_once()
    proc.wait.assert_called_once()


def test_unresponsive_process_is_killed_and_reaped():
    proc = Mock()
    proc.poll.return_value = None
    proc.wait.side_effect = [subprocess.TimeoutExpired('frida', 3), 0]
    ScriptTask._stop_frida_process(proc)
    proc.terminate.assert_called_once()
    proc.kill.assert_called_once()
    assert proc.wait.call_count == 2


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows launcher process tree')
def test_windows_cleanup_targets_only_owned_process_tree(monkeypatch):
    proc = Mock(pid=12345)
    proc.poll.return_value = None
    taskkill = Mock()
    monkeypatch.setattr('tasks.AutoCheckinBigGod.script_task.subprocess.run', taskkill)
    ScriptTask._stop_frida_process(proc)
    assert taskkill.call_args.args[0] == ['taskkill', '/PID', '12345', '/T', '/F']
    proc.wait.assert_called_once()
