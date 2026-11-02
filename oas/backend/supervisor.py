# This module is imported by the supervisor process only: the backend
# child deserializes entry.backend_process_entry (oas.backend.entry),
# so module-level imports here never leak into the backend process.

import multiprocessing
import os
import signal
import stat
import sys
import threading
import time

from oas.backend.entry import backend_process_entry
from oas.backend.mpipe.token_supervisor import SupervisorTokenManager


def loop_until_timeout(timeout):
    end = time.time() + timeout
    while 1:
        yield
        if time.time() >= end:
            break


def mprint(*args, start=''):
    """
    Print a supervisor log line without ever raising on a broken stdout.

    The host process (local Flutter) owns the read end of the supervisor's
    stdout pipe. When the host dies, writing to the pipe raises OSError
    (BrokenPipeError on POSIX, EINVAL on Windows). Logging must never
    abort the supervision or shutdown flow, otherwise a dead host can
    leave the supervisor and its backend running as orphans.

    Args:
        *args: Values printed after the [Supervisor] prefix
        start (str): Prefix inserted before the [Supervisor] marker
    """
    try:
        print(f'{start}[Supervisor]', *args)
    except AttributeError, OSError, ValueError:
        # stdout is missing, closed or its pipe is broken: drop the line
        pass


class ParentProcessExited(Exception):
    """
    Raised when the host process (local Flutter) closed the stdin command channel.

    The supervisor's main loop raises this when the stdin listener observes a
    closed pipe: nobody is left to manage the supervisor, so the backend is
    shut down instead of being left running as an orphan.
    """


class Supervisor:
    def __init__(
        self,
        restart_delay: int = 3,
        max_restart_attempts: int = 10,
        restart_window: int = 60,
        startup_timeout: float = 5.0,
        graceful_shutdown_timeout: float = 5.0,
    ):
        """
        Supervisor process for OAS backend

        Args:
            restart_delay: Seconds to wait before restarting after crash
            max_restart_attempts: Max restarts within restart_window before giving up
            restart_window: Time window (seconds) to count restart attempts
            startup_timeout: Seconds to wait before considering startup successful.
                           If backend crashes within this time, it's a startup failure
                           and supervisor will NOT retry.
            graceful_shutdown_timeout: Seconds to wait for graceful shutdown before
                                      force killing the backend process.
        """
        # The backend process instance
        self.process: 'multiprocessing.Process | None' = None

        # Communication pipe - supervisor's end only
        self.parent_conn: 'multiprocessing.PipeConnection | None' = None

        # Whether this supervisor was started with --flutter. Only then
        # tokens are generated / rotated / announced and FLUTTER=1 is set
        # for the backend chain.
        self.is_flutter = False

        # Guards every parent_conn.send_bytes on the supervisor side:
        # rotation delivery (through the token manager), stdin forwarding
        # and graceful shutdown share one writer lock (concurrent writes
        # on a Pipe corrupt the stream).
        self._send_lock = threading.Lock()

        # Token manager: owns the rotation / announcement state and
        # delegates all pipe writes to send_bytes_to_backend() (the
        # supervisor owns the pipe). Created in __init__ so start_backend
        # and handle_backend_message work standalone; only active in
        # flutter mode (run() calls init_token / start_rotation).
        self.token_manager = SupervisorTokenManager(self)

        # Flag to indicate a restart is requested
        self.restart_requested = False
        # main thread id
        self.main_tid = threading.get_ident()

        # Restart configuration
        self.restart_delay = restart_delay
        self.max_restart_attempts = max_restart_attempts
        self.restart_window = restart_window
        self.startup_timeout = startup_timeout
        self.graceful_shutdown_timeout = graceful_shutdown_timeout

        # Track restart attempts to prevent infinite loops
        self.restart_times = []

        # Track SIGINT count to handle multiple CTRL+C presses
        self.sigint_count = 0

        # Set when a stop is requested through stdin, so the supervisor exits
        # after the backend is gone instead of restarting it
        self.stop_requested = False

        # One-shot resume credential (token-checksum) announced by the backend
        # through command:resume:<credential>. The next start_backend()
        # injects it into the backend child as ALASIO_RESUME_TOKEN; it is
        # cleared once the new backend announced startup completion
        # (command:started), so the credential only serves the spawn chain it
        # was meant for and can never leak into a later independent start.
        self.resume_token = ''

        # stdin listener thread state. The thread must be fully stopped while
        # a backend process is spawning: on Windows, any thread holding the
        # inherited stdin pipe handle (read or wait, even non-blocking) makes
        # multiprocessing spawn hang when duplicating handles into the child.
        # threading.Event is used because the Supervisor instance is no longer
        # pickled into the backend child (the process target is a module-level
        # function), so there is no pickle compatibility constraint.
        self._stdin_stop = threading.Event()
        self._stdin_thread = None

        # Set when the stdin listener observes EOF on a pipe stdin: the
        # parent process (local Flutter) is gone. One-shot and never cleared,
        # parent death is permanent. recv_loop checks it and raises
        # ParentProcessExited to trigger the graceful shutdown.
        self._stdin_eof = threading.Event()

    def _check_restart_limit(self) -> bool:
        """
        Check if we've hit the restart limit within the time window.

        Returns:
            True if restart is allowed, False if limit exceeded
        """
        now = time.time()

        # Clean up old restart times outside the window
        self.restart_times = [
            t for t in self.restart_times if now - t < self.restart_window
        ]

        # Check if we've exceeded max restarts
        if len(self.restart_times) >= self.max_restart_attempts:
            mprint(
                f'ERROR: Backend has crashed {self.max_restart_attempts} times in {self.restart_window} seconds'
            )
            mprint('This indicates a persistent problem. Entering error state...')
            return False

        # Record this restart attempt
        self.restart_times.append(now)
        return True

    def multiprocessing_freeze_support(self):
        """
        For multiprocessing to work correctly on all platforms
        Wrap as method so entry file can be simplified
        """
        multiprocessing.freeze_support()
        return self

    @staticmethod
    def backend_entry(args):
        """
        Subclasses must override this attribute with a module-level function,
        e.g. `backend_entry = entry.backend_entry` in BackendWithSupervisor. The
        function is pickled into the backend child through the spawn args,
        so it must live in a stdlib-only module (oas.backend.entry).

        Args:
            args (list[str] | None):
        """
        pass

    def start_backend(self, args):
        """
        Start the backend process with pipe communication.

        Returns:
            True if backend started successfully, False otherwise
        """
        mprint('Starting backend process...')

        # Cleanup any parent_conn
        if self.parent_conn:
            try:
                self.parent_conn.close()
            except Exception:
                pass
            self.parent_conn = None

        # Run subprocess in spawn mode
        ctx = multiprocessing.get_context('spawn')

        parent_conn, child_conn = ctx.Pipe()
        # Note that we use daemon=False here, because backend needs to spawn workers
        # and python does not allow daemonic processes to have children
        # It's fine without daemon as backend will exit if pipe broken
        # Token window for the new backend (empty without --flutter: the
        # backend token table stays empty and sensitive APIs are locked).
        tokens = self.token_manager.window()
        self.process = ctx.Process(
            target=backend_process_entry,
            args=(child_conn, args, self.backend_entry, tokens),
            name='oas-backend',
            daemon=False,
        )

        # The stdin listener thread must be fully stopped while spawning:
        # on Windows, any thread holding the inherited stdin pipe handle while
        # the child process initializes its stdio makes multiprocessing spawn
        # hang. The thread is restarted by recv_loop once the backend has
        # finished starting up, so buffered commands are not lost.
        self.stop_stdin_listener()
        # FLUTTER=1 must be set before process.start(): multiprocessing
        # spawn inherits the parent environment, so the whole chain
        # (backend → worker → worker children) gets it. Only set in
        # flutter mode.
        if self.is_flutter:
            os.environ['FLUTTER'] = '1'
        # Inject the announced resume credential the same way: only write when
        # the backend announced one, so an inherited value (e.g. passed down
        # by an update relaunch) is never modified without an announcement.
        if self.resume_token:
            os.environ['ALASIO_RESUME_TOKEN'] = self.resume_token
        try:
            self.process.start()
        finally:
            pass

        # close child_conn of the parent side immediately
        child_conn.close()
        self.parent_conn = parent_conn

        mprint(f'Backend running on PID: {self.process.pid}')

    def start_stdin_listener(self):
        """
        Start the daemon thread that listens for commands from stdin.

        Only recognized commands are forwarded to the backend process through
        the pipe, unknown stdin input is silently discarded.

        Recognized commands:
            command:stop        Gracefully stop the backend (also flags the
                                supervisor itself to exit afterwards)
            command:*           Any other command line is forwarded to the
                                backend verbatim; the backend owns the
                                semantics, so a backend update can change
                                command handling without touching this
                                process

        The thread never blocks on a read: it only reads bytes that are
        already available in the pipe, so it always notices the stop event
        within one poll cycle and can be joined by stop_stdin_listener. The
        idle wait lives inside the platform read_available(): Windows sleeps
        one poll cycle after an empty peek, POSIX lets select wait instead
        of sleeping. The listener must be stopped (see stop_stdin_listener)
        while a backend process is spawning, otherwise multiprocessing spawn
        hangs on Windows.

        EOF semantics: when stdin is a pipe, EOF means the parent process
        (local Flutter) closed its write end, i.e. the parent is gone. The
        listener sets _stdin_eof; recv_loop turns that into a
        ParentProcessExited so run() performs the graceful shutdown, which
        sends command:stop to the backend (with a force-kill fallback).
        The listener itself does not send anything: the shutdown path owns
        the stop command, so sending it here would be redundant.
        EOF on non-pipe stdin (console or redirected file) only stops the
        listener, matching the original behavior: parent-death detection
        only applies to the pipe stdin that the local Flutter host provides.

        Returns:
            threading.Thread | None: The listener thread, or None if it was
                already running
        """
        if self._stdin_thread and self._stdin_thread.is_alive():
            return None

        def _stdin_loop():
            try:
                if sys.platform == 'win32':
                    import ctypes
                    import msvcrt

                    fd = sys.stdin.fileno()
                    handle = msvcrt.get_osfhandle(fd)
                    peek = ctypes.windll.kernel32.PeekNamedPipe
                    # Only pipe stdin carries parent-death semantics: the
                    # write end is owned by the host process (local Flutter), so
                    # EOF on a pipe means the parent is gone. Console stdin
                    # is not a pipe and must never trigger shutdown.
                    is_pipe = (
                        ctypes.windll.kernel32.GetFileType(handle) == 3
                    )  # FILE_TYPE_PIPE

                    def read_available():
                        # Non-blocking read of whatever is currently in the
                        # pipe. PeekNamedPipe reports the exact byte count;
                        # reading exactly that many bytes can never block
                        # because the data is already there. On a broken pipe
                        # (EOF) peek fails, so read the leftover and observe
                        # the EOF. Unlike WaitForMultipleObjects this never
                        # reports a pipe as readable when it has no data.
                        # When idle, sleep one poll cycle so the loop does
                        # not busy-spin.
                        count = ctypes.c_ulong(0)
                        ok = peek(handle, None, 0, None, ctypes.byref(count), None)
                        if not ok:
                            count.value = 1
                        if count.value > 0:
                            try:
                                return os.read(fd, count.value)
                            except OSError:
                                return b''
                        time.sleep(0.05)
                        return None
                else:
                    import select

                    fd = sys.stdin.fileno()
                    # POSIX equivalent of the Windows pipe check: only a
                    # FIFO has broken-pipe semantics; terminals and
                    # redirected files must not trigger shutdown.
                    is_pipe = stat.S_ISFIFO(os.fstat(fd).st_mode)

                    def read_available():
                        # select waits up to one poll cycle itself, so idle
                        # waiting needs no separate sleep. A pipe read
                        # returns whatever is available, so it never blocks
                        # after select reported readable.
                        if not select.select([fd], [], [], 0.05)[0]:
                            return None
                        try:
                            return os.read(fd, 4096)
                        except OSError:
                            return b''
            except AttributeError, OSError:
                # No stdin available (e.g. launched without a stdin pipe)
                return

            line_buffer = b''
            while not self._stdin_stop.is_set():
                data = read_available()
                if data is None:
                    continue
                if not data:
                    # EOF: the parent process closed its stdin write end.
                    # Handle a last line that was not terminated by a
                    # newline, then stop.
                    if line_buffer and self._handle_stdin_line(line_buffer):
                        return
                    # On a pipe, EOF means the parent (local Flutter) is gone:
                    # nobody is left to manage this supervisor. Flag the
                    # main loop; recv_loop raises ParentProcessExited and
                    # run() sends command:stop through graceful_shutdown.
                    # The listener only detects, it never sends the stop
                    # itself.
                    if is_pipe:
                        # Flag the parent death before logging: the host's
                        # stdout pipe is broken at this point (the host is
                        # gone), so the log line may fail. The flag is what
                        # drives the shutdown and must be set regardless.
                        self._stdin_eof.set()
                        mprint('Parent process exited (stdin closed), shutting down')
                    return
                line_buffer += data
                while b'\n' in line_buffer:
                    line, _, line_buffer = line_buffer.partition(b'\n')
                    if self._handle_stdin_line(line):
                        return

        self._stdin_stop.clear()
        thread = threading.Thread(
            target=_stdin_loop, name='stdin_listener', daemon=True
        )
        thread.start()
        self._stdin_thread = thread
        return thread

    def _handle_stdin_line(self, line):
        """
        Handle one complete line read from stdin.

        Args:
            line (bytes): Line including the trailing newline unless it is
                the last line of the stream

        Returns:
            bool: True if the listener should stop, False otherwise
        """
        line = line.strip()
        if line.startswith(b'command:'):
            if line == b'command:stop':
                self.stop_requested = True
                if self.parent_conn:
                    try:
                        self.send_bytes_to_backend(line)
                    except EOFError, OSError:
                        # pipe broken, backend is gone, nothing to forward
                        pass
                # Stop requested, no more commands to handle
                return True
            # All other command lines are forwarded to the backend verbatim:
            # the supervisor must not parse command semantics, the backend
            # owns them (a backend update can change command handling
            # without touching this process). The listener keeps running.
            if self.parent_conn:
                try:
                    self.send_bytes_to_backend(line)
                except EOFError, OSError:
                    # pipe broken, backend is gone, nothing to forward
                    pass
            return False
        # Unknown input is silently discarded
        return False

    def send_bytes_to_backend(self, data):
        """
        Send bytes to the backend through the pipe, guarded by the shared
        send lock (rotation delivery, stdin forwarding and graceful
        shutdown are concurrent writers on the same pipe; concurrent
        send_bytes on a multiprocessing Pipe corrupt the stream).

        Args:
            data (bytes):

        Returns:
            bool: True when the message was written, False when no
                backend pipe is attached (no backend running)
        """
        if self.parent_conn is None:
            return False
        with self._send_lock:
            self.parent_conn.send_bytes(data)
        return True

    def stop_stdin_listener(self):
        """
        Stop the stdin listener thread and wait for it to exit.

        Needed before spawning a backend process, see start_stdin_listener.
        The listener never blocks on a read (see start_stdin_listener), so it
        exits within one poll cycle and join always succeeds. This also
        guarantees the daemon thread is gone before the interpreter shuts
        down; a still-running listener would otherwise keep the stdin buffer
        locked and Python aborts with
        "Fatal Python error: could not acquire lock for <_io.BufferedReader>".
        """
        self._stdin_stop.set()
        if self._stdin_thread:
            self._stdin_thread.join(timeout=1)
            self._stdin_thread = None

    def recv_loop(self) -> bool:
        """
        Listen for messages from backend via pipe.

        Uses a timeout on the first recv() to detect startup failures:
        - If backend crashes within startup_timeout: startup failure (return False)
        - If backend survives startup_timeout: startup success (return True)

        This blocks until the pipe is closed (backend exits) or a message arrives.

        Returns:
            True if backend successfully started, False if startup failed
        """
        if not self.parent_conn:
            return False

        startup_success = False
        try:
            # First recv with timeout to detect startup failures
            # If backend crashes within timeout, we'll get EOFError
            # If backend emits a confirmation message, startup succeeded
            # If timeout reached, startup is considered successful
            for _ in loop_until_timeout(timeout=self.startup_timeout):
                if self._stdin_eof.is_set():
                    # The parent process (local Flutter) closed the stdin
                    # command channel while the backend was still
                    # starting: nobody is left to manage this supervisor.
                    # Checked here because command:spawned can already
                    # have started the listener inside this window, so the
                    # EOF must not wait out the window to be acted on.
                    raise ParentProcessExited
                wake = self.parent_conn.poll(timeout=0.2)
                if wake:
                    msg = self.parent_conn.recv_bytes()
                    if msg == b'command:spawned':
                        # Backend child finished spawning (sent from
                        # entry.backend_process_entry right after boot):
                        # the child is past its stdio initialization, so
                        # the stdin listener can safely start. This is NOT
                        # a startup confirmation: the backend has not
                        # finished starting, the window keeps running, and
                        # a crash later in the window (e.g. a bind
                        # conflict) still counts as a startup failure.
                        mprint('Backend spawned, starting stdin listener')
                        self.start_stdin_listener()
                        continue
                    mprint(f'Backend emits message, startup successful')
                    self.handle_backend_message(msg)
                    break
            else:
                mprint(
                    f'Backend running for {self.startup_timeout}s, startup successful'
                )

            startup_success = True

            # The stdin listener can only be started once the child is past
            # its stdio initialization: on Windows, touching the inherited
            # stdin pipe handle while the child process initializes its
            # stdio makes multiprocessing spawn hang. entry.py announces
            # command:spawned as soon as the child is past that point, which
            # starts the listener inside the startup window above; this call
            # is the fallback for backends that never announce (already
            # running listener is a no-op).
            self.start_stdin_listener()

            # wait infinitely
            while 1:
                if self._stdin_eof.is_set():
                    # The parent process (local Flutter) closed the stdin command
                    # channel: it is gone, so nobody is left to manage this
                    # supervisor. Shut the backend down instead of leaving
                    # it running as an orphan.
                    raise ParentProcessExited
                wake = self.parent_conn.poll(timeout=0.2)
                if wake:
                    msg = self.parent_conn.recv_bytes()
                    self.handle_backend_message(msg)

        except EOFError:
            # Pipe closed - backend exited
            if not startup_success:
                mprint('Backend closed pipe connection during startup')
            else:
                mprint('Backend closed pipe connection')
            return startup_success

        except OSError as e:
            # Pipe error
            if not startup_success:
                mprint(f'Pipe error during startup: {e}')
            else:
                mprint(f'Pipe error: {e}')
            return startup_success

    def handle_backend_message(self, msg):
        """
        Handle a message received from the backend.

        Messages are simple byte strings representing commands.

        Args:
            msg (bytes): The message received from backend (expected to be bytes)
        """
        if msg == b'command:restart':
            mprint('Backend requested restart')
            self.restart_requested = True
        elif msg == b'command:stop':
            mprint('Backend requested stop')
            self.handle_sigint(signal.SIGINT, None)
        elif msg == b'command:started':
            # The backend announced that its pipe channel is live (sent by
            # asgi.py's BackendConfig.create_sockets once the listeners are
            # up). Any first
            # backend message ends recv_loop's startup window, which is
            # what starts the stdin listener.
            # The announced resume credential has now served its spawn chain:
            # drop the stored copy and the environment residue, so a later
            # independent spawn can never inherit a stale credential.
            self.resume_token = ''
            os.environ.pop('ALASIO_RESUME_TOKEN', None)
        elif msg == b'command:spawned':
            # Backend child spawn completion announcement (sent from
            # entry.backend_process_entry). Normally received inside
            # recv_loop's startup window, which starts the stdin listener
            # and keeps the window running; this branch only covers the
            # message arriving after the window already ended, where the
            # listener is up already and there is nothing to do.
            pass
        elif msg.startswith(b'command:resume:'):
            # One-shot resume credential announcement (graceful restart or
            # crash takeover): the next start_backend() injects it into the
            # backend child through ALASIO_RESUME_TOKEN. Latest announcement
            # wins, so an empty credential -- the cancel of a restart retracts
            # its publication -- clears the stored one: from then on nothing is
            # injected, whatever the resume file does. A malformed payload is
            # ignored instead of killing the supervision loop.
            try:
                self.resume_token = msg[len(b'command:resume:') :].decode()
            except UnicodeDecodeError as e:
                mprint(f'WARNING: Ignoring malformed resume credential: {e}')
        elif msg.startswith(b'token_ack:'):
            # Backend confirmed a rotated token; wake the rotation thread
            self.token_manager.handle_token_ack(msg)
        else:
            mprint(f'WARNING: Unknown command from backend: {msg}')

    def handle_sigint(self, signum, frame):
        """
        Custom SIGINT handler to track CTRL+C presses.

        - First CTRL+C: Trigger graceful shutdown
        - Second CTRL+C: Trigger force kill
        - Third+ CTRL+C: Ignored (already shutting down)

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        self.sigint_count += 1
        try:
            sig = signal.Signals(signum).name
        except ValueError:
            sig = f'Unknown-signal-{signum}'

        if self.sigint_count == 1:
            # First CTRL+C - trigger graceful shutdown
            mprint(f'Received {sig}, initiating graceful shutdown...', start='\n')
            raise KeyboardInterrupt
        elif self.sigint_count == 2:
            # Second CTRL+C - trigger force kill
            mprint(f'Received {sig}, force killing backend...', start='\n')
            raise KeyboardInterrupt
        else:
            # Third+ CTRL+C - ignore, already shutting down
            mprint(
                f'Already shutting down, please wait... (CTRL+C #{self.sigint_count})',
                start='\n',
            )

    def wait_for_backend(self) -> int:
        """
        Wait for backend process to exit.

        Returns:
            Exit code of the backend process
        """
        if not self.process:
            return -1

        try:
            while 1:
                self.process.join(0.2)
                exitcode = self.process.exitcode
                if exitcode is not None:
                    mprint(f'Backend exited with code: {exitcode}')
                    return exitcode
        except Exception as e:
            mprint(f'Error waiting for backend: {e}')
            return -1

    def graceful_shutdown(self):
        """
        Send 'command:stop' to the backend process.

        Returns:
            bool: If success
        """
        if not self.process or not self.process.is_alive():
            # nothing to kill, consider success
            return True

        if self.parent_conn:
            try:
                self.send_bytes_to_backend(b'command:stop')
            except Exception as e:
                mprint(f'ERROR: Failed to sending stop to backend: {e}')

        # Wait for backend to exit gracefully
        for _ in loop_until_timeout(timeout=self.graceful_shutdown_timeout):
            # interruptable join(), so KeyboardInterrupt can be injected here
            self.process.join(timeout=0.2)
            if not self.process.is_alive():
                break
        else:
            mprint(
                f"Backend didn't shutdown after {self.graceful_shutdown_timeout} seconds, "
                'will force kill in cleanup'
            )
            return False

        # cleanup on success
        self.process = None
        self._cleanup_conn()

    def force_shutdown(self):
        """
        Returns:
            bool: If success
        """
        if not self.process or not self.process.is_alive():
            # nothing to kill, consider success
            return True

        try:
            self.process.kill()
            self.process.join(timeout=2)
            mprint('Backend force killed')
        except Exception as e:
            mprint(f'ERROR: Failed to force kill backend: {e}')
            return False

        # cleanup on success
        self.process = None
        self._cleanup_conn()

    def _cleanup_conn(self):
        if self.parent_conn:
            try:
                self.parent_conn.close()
            except Exception:
                pass
            self.parent_conn = None

    def cleanup(self):
        """
        Clean up resources and ensure backend is terminated.
        """
        if self.process:
            if self.process.is_alive():
                mprint('Terminating backend process...')
                try:
                    self.process.terminate()
                    self.process.join(timeout=5)

                    if self.process.is_alive():
                        mprint("Backend didn't terminate, force killing...")
                        self.process.kill()
                        self.process.join()

                except Exception as e:
                    mprint(f'Error during cleanup: {e}')

            self.process = None

        # Clean up pipe
        self._cleanup_conn()

    def run(self, args=None):
        """
        Main supervisor loop.

        Simplified control flow using exceptions:
        - Normal flow: start backend, listen to pipe, handle restart
        - CTRL+C: KeyboardInterrupt caught, graceful shutdown
        - Errors: caught and handled appropriately

        Args:
            args (list[str] | None):
        """
        # backend entry should not be placeholder
        if self.backend_entry == Supervisor.backend_entry:
            mprint('ERROR: backend entry is still placeholder, nothing to run')
            return

        mprint(f'Running on PID: {os.getpid()}')

        # Flutter mode: generate and announce T1, start the rotation
        # thread. Without --flutter no token is generated: the backend
        # token table stays empty and sensitive APIs are locked.
        self.is_flutter = bool(args) and '--flutter' in args
        if self.is_flutter:
            self.token_manager.init_token()
            self.token_manager.start_rotation()

        # Set up custom SIGINT handler to track CTRL+C count
        signal.signal(signal.SIGINT, self.handle_sigint)
        signal.signal(signal.SIGTERM, self.handle_sigint)
        if sys.platform == 'win32':
            signal.signal(signal.SIGBREAK, self.handle_sigint)

        # The stdin listener thread ("command:stop" from the Flutter host) is started
        # and stopped by start_backend around every spawn

        try:
            # Main supervision loop
            while True:
                # Start the backend
                self.cleanup()
                self.start_backend(args)

                # Listen for messages from backend
                # This blocks until backend exits (pipe closes)
                startup_success = self.recv_loop()
                self.wait_for_backend()

                # The parent process is gone; never start another backend
                if self._stdin_eof.is_set():
                    mprint('Parent process exited (stdin closed), exiting')
                    break

                # Stop was requested through stdin, exit without restarting
                if self.stop_requested:
                    mprint('Stop requested through stdin, exiting')
                    break

                # Check if this was a startup failure
                if not startup_success:
                    mprint('ERROR: Backend failed to start properly')
                    break

                # Check if restart was requested by backend
                if self.restart_requested:
                    self.restart_requested = False
                    continue

                # Check if we should restart or enter error state
                if not self._check_restart_limit():
                    mprint(
                        f'Restart limit exceeded '
                        f'({self.restart_times} times in {self.max_restart_attempts} seconds)'
                    )
                    break

                mprint(f'Restarting in {self.restart_delay} seconds...')
                for _ in loop_until_timeout(timeout=self.restart_delay):
                    # The host may die or request a stop during the delay:
                    # never spawn a backend that nobody is left to manage.
                    if self._stdin_eof.is_set() or self.stop_requested:
                        break
                    time.sleep(0.2)
                if self._stdin_eof.is_set() or self.stop_requested:
                    break
                continue

        except KeyboardInterrupt, ParentProcessExited:
            # First CTRL+C, or the parent process exited: initiate graceful
            # shutdown
            try:
                if not self.graceful_shutdown():
                    self.force_shutdown()
            except KeyboardInterrupt:
                # Second CTRL+C - force kill immediately
                self.force_shutdown()

        except Exception as e:
            mprint(f'Unexpected error: {e}', start='\n')
            import traceback

            traceback.print_exc()

        finally:
            # Always clean up
            self.cleanup()
            # The stdin listener is a daemon thread; if it is still running
            # when the interpreter shuts down, Python aborts with
            # "Fatal Python error: could not acquire lock ..." because the
            # thread holds the stdin buffer lock. Stop it before returning.
            self.stop_stdin_listener()
            mprint('Supervisor loop ended')
