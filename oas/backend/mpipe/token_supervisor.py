import collections
import secrets
import threading
import time

# Rotation interval in seconds (30min+). The rotation
# thread only runs when the supervisor was started with --flutter.
ROTATION_INTERVAL = 1800
# Seconds to wait for the backend ack before dropping the rotation round
ACK_TIMEOUT = 2.0


class SupervisorTokenManager:
    """
    Supervisor-side token manager. One instance per supervisor, created
    by Supervisor.run() with the owning supervisor object. Only active
    when the supervisor was started with --flutter; otherwise it
    generates nothing and the backend token table stays empty (sensitive
    APIs locked).

    The supervisor is the single source of truth for tokens: it
    generates, holds, rotates, sends down the pipe and announces them;
    the local Flutter app only listens to the announcements and never inputs a token.
    The memory window only ever contains tokens that were both announced
    to the local Flutter app and confirmed (token_ack) by the backend (T1 is the
    exception: it is announced before the backend is born).

    All pipe writes are delegated to the supervisor's
    send_bytes_to_backend() (which holds the supervisor-side send lock):
    this manager never touches parent_conn directly.
    """

    def __init__(self, supervisor):
        """
        Args:
            supervisor (Supervisor): The owning supervisor; pipe writes
                go through supervisor.send_bytes_to_backend()
        """
        self._supervisor = supervisor
        self._window: 'collections.deque[str]' = collections.deque(maxlen=2)
        # Rotation ACK handover between the rotation thread and recv_loop
        self._pending_lock = threading.Lock()
        self._pending_token: 'str | None' = None
        self._pending_ack: 'threading.Event | None' = None
        self._rotation_thread: 'threading.Thread | None' = None

    def init_token(self):
        """
        Generate T1 and announce it (the backend is not born yet).

        The announcement must use print, not logger: the logger is muted
        in local Flutter mode (FLUTTER=1) and would swallow the announcement.
        """
        token = secrets.token_hex(32)
        self._window.append(token)
        # flush: the announcement must reach the local Flutter app immediately even
        # though python block-buffers stdout on a pipe
        print(f'[Supervisor] token_set:begin:{token}', flush=True)

    def window(self):
        """
        Token window for spawn args (backend restart continuity).

        Returns:
            tuple[str]: 0~2 announced-and-acked tokens
        """
        return tuple(self._window)

    def start_rotation(self):
        """
        Start the daemon rotation thread. No-op without --flutter.
        """
        if self._rotation_thread and self._rotation_thread.is_alive():
            return
        self._rotation_thread = threading.Thread(
            target=self._rotation_loop, daemon=True, name='token_rotation'
        )
        self._rotation_thread.start()

    def _rotation_loop(self):
        while True:
            time.sleep(ROTATION_INTERVAL)
            self.rotate()

    def rotate(self):
        """
        Send the new token down the pipe, wait for the backend ack, then
        announce. Never announce an unconfirmed token.

        On failure (backend not attached / pipe broken / ack timeout) the
        round is dropped: the pending state is reset and the local Flutter app stays on
        the old token. The next round or a backend restart (args carry the
        old window) converges naturally.
        """
        token = secrets.token_hex(32)
        ack = threading.Event()
        with self._pending_lock:
            self._pending_token = token
            self._pending_ack = ack

        try:
            if not self._supervisor.send_bytes_to_backend(b'token:' + token.encode()):
                # backend not attached yet (rotation thread may start
                # before the first backend spawn); skip this round
                self._reset_pending()
                return
        except EOFError, OSError:
            # backend gone; skip this round
            self._reset_pending()
            return

        if ack.wait(timeout=ACK_TIMEOUT):
            # old = the previous announced token inside the window
            old = self._window[-1] if self._window else ''
            self._window.append(token)
            # flush: the announcement must reach the local Flutter app immediately even
            # though python block-buffers stdout on a pipe
            print(f'[Supervisor] token_set:{old}:{token}', flush=True)
        else:
            # ack timeout: drop the token, the local Flutter app stays on the old one
            pass
        self._reset_pending()

    def _reset_pending(self):
        with self._pending_lock:
            self._pending_token = None
            self._pending_ack = None

    def handle_token_ack(self, msg):
        """
        Called by recv_loop on a token_ack:<token> message.

        Args:
            msg (bytes): The raw message received from the backend
        """
        token = msg[10:].decode()
        with self._pending_lock:
            if self._pending_ack and token == self._pending_token:
                self._pending_ack.set()
