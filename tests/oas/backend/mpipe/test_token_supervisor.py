import re
import threading

from oas.backend.mpipe.token_supervisor import SupervisorTokenManager


class FakeSupervisor:
    """
    A fake supervisor for token manager tests: records the bytes written
    through send_bytes_to_backend() and lets the test resolve the
    pending ack manually.
    """

    def __init__(self, connected=True):
        self.sent: 'list[bytes]' = []
        self.connected = connected

    def send_bytes_to_backend(self, data):
        if not self.connected:
            return False
        self.sent.append(bytes(data))
        return True


class BrokenSupervisor(FakeSupervisor):
    """send_bytes_to_backend raises (pipe broken)."""

    def send_bytes_to_backend(self, data):
        raise OSError('broken pipe')


class TestSupervisorTokenManagerInit:
    def test_init_token_announces_begin_format(self, capsys):
        """T1 announcement must use the chained begin format and print."""
        manager = SupervisorTokenManager(FakeSupervisor())
        manager.init_token()
        captured = capsys.readouterr()
        match = re.fullmatch(
            r'\[Supervisor\] token_set:begin:([0-9a-f]{64})\n', captured.out
        )
        assert match is not None
        assert manager.window() == (match.group(1),)

    def test_window_is_tuple(self):
        """window() returns the current announced-and-acked tokens."""
        manager = SupervisorTokenManager(FakeSupervisor())
        assert manager.window() == ()
        manager.init_token()
        assert len(manager.window()) == 1
        assert isinstance(manager.window(), tuple)

    def test_supervisor_is_held(self):
        """The owning supervisor is stored for pipe writes."""
        supervisor = FakeSupervisor()
        manager = SupervisorTokenManager(supervisor)
        assert manager._supervisor is supervisor


class TestSupervisorTokenManagerRotate:
    def test_rotate_announces_after_ack(self, capsys):
        """rotate() announces token_set:<old>:<new> only when acked."""
        supervisor = FakeSupervisor()
        manager = SupervisorTokenManager(supervisor)
        manager.init_token()
        old_token = manager.window()[0]
        capsys.readouterr()

        # resolve the ack synchronously inside rotate: emulate the backend
        # by hooking send_bytes_to_backend to immediately ack
        original = supervisor.send_bytes_to_backend

        def send_and_ack(data):
            original(data)
            token = data[6:].decode()
            manager.handle_token_ack(b'token_ack:' + token.encode())
            return True

        supervisor.send_bytes_to_backend = send_and_ack
        manager.rotate()

        captured = capsys.readouterr()
        match = re.fullmatch(
            r'\[Supervisor\] token_set:([0-9a-f]{64}):([0-9a-f]{64})\n', captured.out
        )
        assert match is not None
        assert match.group(1) == old_token
        # new token appended to the window
        assert manager.window() == (old_token, match.group(2))

    def test_rotate_ack_timeout_drops_round(self, capsys, monkeypatch):
        """On ack timeout the round is dropped: no announce, no window grow."""
        supervisor = FakeSupervisor()
        manager = SupervisorTokenManager(supervisor)
        manager.init_token()
        old_token = manager.window()[0]
        capsys.readouterr()

        # monkeypatch the ack wait to always time out
        monkeypatch.setattr(threading.Event, 'wait', lambda self, timeout: False)
        manager.rotate()

        captured = capsys.readouterr()
        assert captured.out == ''
        # token was sent down the pipe
        assert supervisor.sent[0].startswith(b'token:')
        # window unchanged, pending state cleared
        assert manager.window() == (old_token,)
        assert manager._pending_token is None
        assert manager._pending_ack is None

    def test_rotate_without_attach_skips_round(self, capsys):
        """No backend pipe: skip the round, reset pending, no announce."""
        supervisor = FakeSupervisor(connected=False)
        manager = SupervisorTokenManager(supervisor)
        manager.init_token()
        capsys.readouterr()
        manager.rotate()
        captured = capsys.readouterr()
        assert captured.out == ''
        assert supervisor.sent == []
        assert manager._pending_token is None
        assert manager._pending_ack is None

    def test_rotate_send_failure_skips_round(self, capsys):
        """Pipe broken (OSError): skip the round, no announce."""
        supervisor = BrokenSupervisor()
        manager = SupervisorTokenManager(supervisor)
        manager.init_token()
        old_token = manager.window()[0]
        capsys.readouterr()
        manager.rotate()
        captured = capsys.readouterr()
        assert captured.out == ''
        assert manager.window() == (old_token,)
        assert manager._pending_token is None

    def test_window_maxlen_2(self):
        """The window keeps at most 2 announced tokens."""
        supervisor = FakeSupervisor()
        manager = SupervisorTokenManager(supervisor)
        manager.init_token()
        first = manager.window()[0]

        # auto-ack on every send
        def send_and_ack(data):
            supervisor.sent.append(bytes(data))
            token = data[6:].decode()
            manager.handle_token_ack(b'token_ack:' + token.encode())
            return True

        supervisor.send_bytes_to_backend = send_and_ack
        manager.rotate()
        second = manager.window()[-1]
        manager.rotate()
        third = manager.window()[-1]
        assert manager.window() == (second, third)
        assert first not in manager.window()

    def test_handle_token_ack_matching_sets_event(self):
        """handle_token_ack with the pending token sets the ack event."""
        manager = SupervisorTokenManager(FakeSupervisor())
        ack = threading.Event()
        with manager._pending_lock:
            manager._pending_token = 'abc'
            manager._pending_ack = ack
        manager.handle_token_ack(b'token_ack:abc')
        assert ack.is_set()

    def test_handle_token_ack_clears_after_timeout(self):
        """A stale ack arriving after the round was dropped is ignored."""
        manager = SupervisorTokenManager(FakeSupervisor(connected=False))
        manager.rotate()  # no pipe: round dropped synchronously
        manager.handle_token_ack(b'token_ack:whatever')
        assert manager._pending_token is None
        assert manager._pending_ack is None


class TestRotationThread:
    def test_start_rotation_starts_daemon_thread(self):
        """start_rotation() spawns a daemon thread running the loop."""
        manager = SupervisorTokenManager(FakeSupervisor())
        manager.start_rotation()
        assert manager._rotation_thread is not None
        assert manager._rotation_thread.is_alive()
        assert manager._rotation_thread.daemon
