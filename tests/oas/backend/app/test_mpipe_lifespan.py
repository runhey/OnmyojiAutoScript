"""
MPipe receive loop and token rotation tests of the backend lifespan.

The receive loop is the only reader of the supervisor pipe. It runs on a daemon
thread without an async context of its own, so every hand-off back to the loop
is part of the behaviour under test: a shutdown that is never signalled leaves
the backend running as an orphan after its supervisor died, a rotation that is
never delivered leaves the local Flutter client on a token the table has
dropped, and one stuck connection must not hold the notification of the others.
The token ack is the other direction: a supervisor keeps rotating the token
window only while the backend confirms what it received.

Both shapes of the loop are exercised: through ``start_mpipe_recv_thread`` (the
production thread, with a bound loop it can reach) and by calling
``mpipe_recv_loop`` directly with a scripted pipe.
"""

import asyncio
import builtins
import queue
import threading
import time

import anyio
import pytest

from oas.backend.anyio import AnyIO
from oas.backend.app import lifespan as lifespan_module
from oas.backend.app.lifespan import (
    _notify_rotation,
    announce_started,
    mpipe_recv_loop,
    notify_rotation,
    start_mpipe_recv_thread,
    stop_mpipe_recv_thread,
)
from oas.backend.app.restart.restart_manager import RESTART_MANAGER
from oas.backend.mpipe.mpipe_backend import has_supervisor, mpipe_backend
from oas.backend.mpipe.token_backend import token_table
from oas.backend.reactive.event import ResponseEvent
from oas.backend.ws.context import GLOBAL_CONTEXT
from oas.backend.ws.ws_server import WebsocketTopicServer
from oas.logger import logger

RECV_THREAD_NAME = 'mpipe_child_recv'


@pytest.fixture(autouse=True)
def clean_mpipe_state(monkeypatch):
    """
    Run every test on an empty pipe slot, token window and registry, then put
    the process-wide state back.

    ``builtins.__mpipe_conn__`` is the pipe slot a supervisor plants,
    ``token_table._tokens`` the real token window and
    ``WebsocketTopicServer.active`` the real connection registry: all three
    outlive a single test and would leak into the suites that share the process.
    """
    monkeypatch.delattr(builtins, '__mpipe_conn__', raising=False)
    tokens = dict(token_table._tokens)
    token_table._tokens.clear()
    active = dict(WebsocketTopicServer.active)
    WebsocketTopicServer.active.clear()
    yield
    token_table._tokens.clear()
    token_table._tokens.update(tokens)
    WebsocketTopicServer.active.clear()
    WebsocketTopicServer.active.update(active)
    GLOBAL_CONTEXT.shutdown_event = None
    AnyIO.unbind_loop()


def live_recv_threads():
    """
    The live mpipe receive threads of the process

    Returns:
        list[Thread]: Threads named mpipe_child_recv
    """
    return [t for t in threading.enumerate() if t.name == RECV_THREAD_NAME]


def register_active(*servers):
    """
    Put connections into the registry ``notify_rotation`` reads

    Args:
        *servers (FakeServer): Connections to register
    """
    for server in servers:
        WebsocketTopicServer.active[server.id] = server


class _EndOfScript(Exception):
    """
    Ends a scripted receive loop from the test.

    The loop only leaves on the supervisor stop command or on a pipe error;
    any other exception raised by ``recv_bytes`` propagates out of
    ``mpipe_recv_loop``, which is the clean exit a scripted test needs when it
    wants the loop to end without asking for a shutdown.
    """


class ScriptedConn:
    """
    A supervisor pipe stub that hands out a fixed script of messages.

    ``recv_bytes`` returns the scripted messages in order and then raises the
    scripted error, so the loop sees the pipe break the way it does when a
    supervisor exits. ``send_bytes`` records what the backend wrote back.

    Args:
        messages (iterable[bytes]): Messages to hand out, in order
        error (type[Exception]): Raised once the script is exhausted
    """

    def __init__(self, messages=(), error=EOFError):
        self._messages = list(messages)
        self._error = error
        self.sent = []

    def recv_bytes(self):
        if self._messages:
            return self._messages.pop(0)
        raise self._error

    def send_bytes(self, data):
        self.sent.append(bytes(data))


class BlockingConn:
    """
    A supervisor pipe stub that blocks in ``recv_bytes`` until the test feeds
    it, the way the pipe of a live supervisor does.

    ``arm_ack`` returns an event that fires on the next ``send_bytes``, so a
    test can wait for an ack without polling.
    """

    def __init__(self):
        self.inbox = queue.Queue()
        self.sent = []
        self.arm_ack()

    def arm_ack(self):
        """
        Arm a fresh event that fires on the next write to the pipe

        Returns:
            threading.Event: Set by the next send_bytes
        """
        self.acked = threading.Event()
        return self.acked

    def feed(self, message):
        """
        Hand the loop its next message, or the exception to raise on the read

        Args:
            message (bytes | BaseException): Message the next ``recv_bytes``
                returns, or the exception it raises instead
        """
        self.inbox.put(message)

    def recv_bytes(self):
        item = self.inbox.get()
        if isinstance(item, BaseException):
            raise item
        return item

    def send_bytes(self, data):
        self.sent.append(bytes(data))
        self.acked.set()


class RestrictedTopic:
    """A topic only the local Flutter client may subscribe (rotation-relevant)"""

    REQUIRE_LOCAL_FLUTTER = True


class OrdinaryTopic:
    """An ordinary topic: its subscribers never need a token renewal"""

    REQUIRE_LOCAL_FLUTTER = False


class FakeServer:
    """
    A ws connection stub that records what the rotation notification sends it.

    ``notify_rotation`` reads the restriction of a connection through
    ``type(server).ALL_TOPIC_CLASS``, so the restricted / ordinary split of the
    real server is reproduced on the class. ``arm_notify`` returns an event the
    test can await instead of polling the records.

    Args:
        name (str): Connection id, used for the registry and ``__str__``
        local_token (str): Token carried by the handshake
        subscribed (tuple[str]): Subscribed topic names
    """

    ALL_TOPIC_CLASS = {'restricted': RestrictedTopic, 'ordinary': OrdinaryTopic}

    def __init__(
        self,
        name,
        local_token='',
        subscribed=(),
        send_error=None,
        close_error=None,
        send_blocking=False,
    ):
        self.id = name
        self.local_token = local_token
        # notify_rotation only intersects the keys, the values are never read
        self.subscribed = {topic: None for topic in subscribed}
        self.sent = []
        self.closed = []
        self.notified = None
        self._send_error = send_error
        self._close_error = close_error
        self._send_blocking = send_blocking

    def __str__(self):
        return f'FakeServer({self.id})'

    def arm_notify(self):
        """
        Arm a fresh event that fires on the next send or close

        Returns:
            anyio.Event: Set by the next notification of this connection
        """
        self.notified = anyio.Event()
        return self.notified

    async def send(self, data):
        if self._send_blocking:
            # a connection whose send never completes (send buffer back-pressure)
            await anyio.sleep_forever()
        if self._send_error is not None:
            raise self._send_error
        self.sent.append(data)
        self._set_notified()

    async def close(self, code=1000, reason=None):
        if self._close_error is not None:
            raise self._close_error
        self.closed.append((code, reason))
        self._set_notified()

    def _set_notified(self):
        if self.notified is not None:
            self.notified.set()


def test_start_recv_thread_without_a_supervisor_starts_nothing():
    """
    A backend running without a supervisor has no pipe to read, so the lifespan
    gets None (nothing to join at shutdown) and no thread is left behind.
    """
    assert mpipe_backend.conn is None
    before = live_recv_threads()
    assert start_mpipe_recv_thread() is None
    assert live_recv_threads() == before


def test_start_recv_thread_reads_tokens_and_stops_on_the_stop_command(monkeypatch):
    """
    With a supervisor the lifespan owns a daemon receive thread: a rotated
    token lands in the table and is acknowledged back, and the stop command ends
    the thread and drops the pipe, so every maintenance gate closes before the
    process goes down.
    """

    async def main():
        AnyIO.bind_loop(asyncio.get_running_loop())
        shutdown_event = anyio.Event()
        GLOBAL_CONTEXT.shutdown_event = shutdown_event

        conn = BlockingConn()
        monkeypatch.setattr(builtins, '__mpipe_conn__', conn, raising=False)
        aborts = []

        async def abort(self):
            aborts.append(True)

        monkeypatch.setattr(type(RESTART_MANAGER), 'abort', abort)

        thread = start_mpipe_recv_thread()
        assert thread is not None
        assert thread.name == 'mpipe_child_recv'
        assert thread.daemon is True
        assert thread.is_alive() is True

        acked = conn.arm_ack()
        conn.feed(b'token:T2')
        assert await anyio.to_thread.run_sync(acked.wait, 5) is True
        assert token_table.verify('T2') is True
        assert conn.sent == [b'token_ack:T2']

        conn.feed(b'command:stop')
        with anyio.fail_after(5):
            await anyio.to_thread.run_sync(thread.join, 4)
            await shutdown_event.wait()

        assert thread.is_alive() is False
        assert aborts == [True]
        assert mpipe_backend.conn is None
        assert has_supervisor() is False

    anyio.run(main)


def test_start_recv_thread_rotation_notifies_the_restricted_connection(monkeypatch):
    """
    A token message drives the whole rotation: the connection that still holds a
    token of the window is asked to renew, and it is closed with 4002 once the
    rotation has moved past its token.
    """

    async def main():
        AnyIO.bind_loop(asyncio.get_running_loop())
        GLOBAL_CONTEXT.shutdown_event = anyio.Event()

        conn = BlockingConn()
        monkeypatch.setattr(builtins, '__mpipe_conn__', conn, raising=False)

        async def abort(self):
            pass

        monkeypatch.setattr(type(RESTART_MANAGER), 'abort', abort)

        # the window of the backend token table is two entries wide
        token_table.seed_from_supervisor(('T1',))
        client = FakeServer('client', local_token='T1', subscribed=('restricted',))
        register_active(client)

        thread = start_mpipe_recv_thread()
        assert thread is not None
        try:
            renewed = client.arm_notify()
            conn.feed(b'token:T2')
            with anyio.fail_after(5):
                await renewed.wait()
            # T1 is still in the window {T1, T2}: the client may renew
            assert client.sent == [ResponseEvent(t='auth', o='full', v='renew')]
            assert client.closed == []

            rotated = client.arm_notify()
            conn.feed(b'token:T3')
            with anyio.fail_after(5):
                await rotated.wait()
            # the window moved on to {T2, T3}: T1 was evicted
            assert client.sent == [ResponseEvent(t='auth', o='full', v='renew')]
            assert client.closed == [(4002, 'token rotated')]

            conn.feed(b'command:stop')
            with anyio.fail_after(5):
                await anyio.to_thread.run_sync(thread.join, 4)
        finally:
            # never leave the daemon thread blocked on a test queue
            conn.feed(_EndOfScript)
            await anyio.to_thread.run_sync(thread.join, 4)

        assert token_table.verify('T1') is False
        assert token_table.verify('T2') is True
        assert token_table.verify('T3') is True

    anyio.run(main)


def test_recv_loop_token_message_adds_the_token_and_acks(monkeypatch):
    """
    The token of a rotation must land in the table and be acknowledged: the ack
    is what tells the supervisor the backend can serve the new window.
    """
    conn = ScriptedConn([b'token:T2'])
    monkeypatch.setattr(builtins, '__mpipe_conn__', conn, raising=False)

    # ends on the EOFError the script raises after the token message
    mpipe_recv_loop(conn)

    assert token_table.verify('T2') is True
    assert conn.sent == [b'token_ack:T2']


def test_recv_loop_stop_command_aborts_the_flow_and_signals_the_shutdown(monkeypatch):
    """
    The supervisor stop command is the graceful shutdown path: the maintenance
    flow in flight is aborted, the shutdown event is set (this is what the ASGI
    shutdown listener waits on) and the pipe is dropped so nothing can restart
    the backend.
    """

    async def main():
        AnyIO.bind_loop(asyncio.get_running_loop())
        shutdown_event = anyio.Event()
        GLOBAL_CONTEXT.shutdown_event = shutdown_event

        conn = ScriptedConn([b'command:stop'])
        monkeypatch.setattr(builtins, '__mpipe_conn__', conn, raising=False)
        aborts = []

        async def abort(self):
            aborts.append(True)

        monkeypatch.setattr(type(RESTART_MANAGER), 'abort', abort)

        with anyio.fail_after(5):
            await anyio.to_thread.run_sync(mpipe_recv_loop, conn)
            await shutdown_event.wait()

        assert aborts == [True]
        assert mpipe_backend.conn is None
        assert has_supervisor() is False

    anyio.run(main)


def test_recv_loop_pipe_error_shuts_the_backend_down(monkeypatch):
    """
    A broken pipe means the supervisor is gone: the backend must shut itself
    down instead of running as an orphan. An OSError reaches the same branch as
    the EOFError of a closed pipe.
    """

    async def main():
        AnyIO.bind_loop(asyncio.get_running_loop())
        shutdown_event = anyio.Event()
        GLOBAL_CONTEXT.shutdown_event = shutdown_event

        conn = ScriptedConn([], error=OSError('pipe closed'))
        monkeypatch.setattr(builtins, '__mpipe_conn__', conn, raising=False)

        async def abort(self):
            pass

        monkeypatch.setattr(type(RESTART_MANAGER), 'abort', abort)

        with anyio.fail_after(5):
            await anyio.to_thread.run_sync(mpipe_recv_loop, conn)
            await shutdown_event.wait()

        assert mpipe_backend.conn is None
        assert has_supervisor() is False

    anyio.run(main)


def test_recv_loop_signals_the_shutdown_even_when_the_abort_fails(monkeypatch):
    """
    Aborting the maintenance flow is best effort: a backend whose supervisor
    died may not stay up just because that abort failed, so the shutdown signal
    must go out either way. The failure itself still has to be reported: upstream
    ``trio.from_thread.run`` re-raises the coroutine's exception into the receive
    thread, so an abort error must reach the log instead of dying in a future
    nobody reads.
    """

    async def main():
        AnyIO.bind_loop(asyncio.get_running_loop())
        shutdown_event = anyio.Event()
        GLOBAL_CONTEXT.shutdown_event = shutdown_event

        conn = ScriptedConn([b'command:stop'])
        monkeypatch.setattr(builtins, '__mpipe_conn__', conn, raising=False)

        async def abort(self):
            raise RuntimeError('abort failed')

        monkeypatch.setattr(type(RESTART_MANAGER), 'abort', abort)

        with anyio.fail_after(5):
            await anyio.to_thread.run_sync(mpipe_recv_loop, conn)
            await shutdown_event.wait()

        assert mpipe_backend.conn is None

    with logger.mock_capture_writer() as capture:
        anyio.run(main)

    assert capture.backend.any_contains(
        'Failed to abort the maintenance flow: abort failed'
    )


def test_recv_loop_unknown_message_only_warns(monkeypatch):
    """
    An unknown supervisor message is logged and skipped: it must neither shut the
    backend down nor drop the pipe, or a single unrecognized command would kill a
    serving backend.
    """

    async def main():
        AnyIO.bind_loop(asyncio.get_running_loop())
        shutdown_event = anyio.Event()
        GLOBAL_CONTEXT.shutdown_event = shutdown_event

        # deliberately a command nothing handles: the three host stdin commands
        # will gain their own branches when app/prefs.py is ported, so they must
        # not be used as the "unknown" case here
        conn = ScriptedConn([b'command:whatever'], error=_EndOfScript)
        monkeypatch.setattr(builtins, '__mpipe_conn__', conn, raising=False)

        try:
            with anyio.fail_after(5):
                await anyio.to_thread.run_sync(mpipe_recv_loop, conn)
        except _EndOfScript:
            # the script stub ends the blocking loop
            pass

        # let every callback the loop scheduled run before looking at the event
        await anyio.sleep(0)
        return shutdown_event

    with logger.mock_capture_writer() as capture:
        shutdown_event = anyio.run(main)

    assert capture.backend.any_contains('unknown msg from supervisor')
    assert shutdown_event.is_set() is False
    assert has_supervisor() is True


def test_notify_rotation_renews_closes_and_skips():
    """
    One rotation pass must reach exactly the connections that hold a restricted
    subscription: the ones whose token is still in the window are asked to
    renew, the ones whose token was evicted are closed with 4002, and an
    ordinary connection is left untouched.
    """

    async def main():
        valid = FakeServer('valid', local_token='T2', subscribed=('restricted',))
        evicted = FakeServer('evicted', local_token='T1', subscribed=('restricted',))
        ordinary = FakeServer('ordinary', local_token='T2', subscribed=('ordinary',))
        plain = FakeServer('plain', local_token='T2')
        register_active(valid, evicted, ordinary, plain)
        token_table.seed_from_supervisor(('T2',))

        await notify_rotation()

        assert valid.sent == [ResponseEvent(t='auth', o='full', v='renew')]
        assert valid.closed == []
        assert evicted.sent == []
        assert evicted.closed == [(4002, 'token rotated')]
        # no restricted subscription: never a renewal, never a close
        assert ordinary.sent == []
        assert ordinary.closed == []
        assert plain.sent == []
        assert plain.closed == []

    anyio.run(main)


def test_notify_rotation_survives_a_broken_connection():
    """
    A single broken connection must not abort the notification of the others:
    the failure is logged and the remaining connections still get their renew.
    """

    async def main():
        broken = FakeServer(
            'broken',
            local_token='T2',
            subscribed=('restricted',),
            send_error=RuntimeError('pipe gone'),
        )
        good = FakeServer('good', local_token='T2', subscribed=('restricted',))
        register_active(broken, good)
        token_table.seed_from_supervisor(('T2',))

        await notify_rotation()

        assert broken.sent == []
        assert good.sent == [ResponseEvent(t='auth', o='full', v='renew')]

    with logger.mock_capture_writer() as capture:
        anyio.run(main)

    assert capture.backend.any_contains('Rotation notify failed for FakeServer(broken)')


def test_notify_rotation_survives_a_broken_close():
    """
    The closing half has the same guarantee: an evicted connection whose close
    raises must not keep the other evicted connections from being closed.
    """

    async def main():
        broken = FakeServer(
            'broken',
            local_token='T1',
            subscribed=('restricted',),
            close_error=RuntimeError('close failed'),
        )
        good = FakeServer('good', local_token='T1', subscribed=('restricted',))
        register_active(broken, good)
        token_table.seed_from_supervisor(('T2',))

        await notify_rotation()

        assert broken.closed == []
        assert good.closed == [(4002, 'token rotated')]

    with logger.mock_capture_writer() as capture:
        anyio.run(main)

    assert capture.backend.any_contains('Rotation notify failed for FakeServer(broken)')


def test_notify_rotation_timeout_does_not_stall_the_others(monkeypatch):
    """
    A connection whose send never completes is bounded by the per-connection
    timeout: the pass gives up on it and the other connections are notified
    within the same pass instead of waiting for it forever.
    """
    monkeypatch.setattr(lifespan_module, 'ROTATION_NOTIFY_TIMEOUT', 0.05)

    async def main():
        stuck = FakeServer(
            'stuck',
            local_token='T2',
            subscribed=('restricted',),
            send_blocking=True,
        )
        good = FakeServer('good', local_token='T2', subscribed=('restricted',))
        register_active(stuck, good)
        token_table.seed_from_supervisor(('T2',))

        start = time.monotonic()
        with anyio.fail_after(5):
            await notify_rotation()
        return good, time.monotonic() - start

    with logger.mock_capture_writer() as capture:
        good, elapsed = anyio.run(main)

    assert good.sent == [ResponseEvent(t='auth', o='full', v='renew')]
    assert capture.backend.any_contains('Rotation notify timeout for FakeServer(stuck)')
    assert elapsed < 1.0


def test_notify_rotation_bridge_without_a_loop_is_absorbed():
    """
    The recv thread asks for the notification after the loop is already gone
    (the process is shutting down): the bridge must absorb that instead of
    raising into the receive loop.
    """
    AnyIO.unbind_loop()
    assert AnyIO._loop is None

    server = FakeServer('client', local_token='T2', subscribed=('restricted',))
    register_active(server)
    token_table.seed_from_supervisor(('T2',))

    assert _notify_rotation() is None
    # nothing was notified: there was no loop to run notify_rotation on
    assert server.sent == []
    assert server.closed == []


def test_announce_started_confirms_the_pipe(monkeypatch):
    """
    The startup confirmation is what makes the supervisor treat the backend as
    up, so it must reach the pipe right away.
    """
    conn = ScriptedConn()
    monkeypatch.setattr(builtins, '__mpipe_conn__', conn, raising=False)

    assert announce_started() is None
    assert conn.sent == [b'command:started']


def test_announce_started_without_a_supervisor_is_silent():
    """
    Running without a supervisor, the startup confirmation has nowhere to go:
    the non-strict send drops it instead of raising into the startup path.
    """
    assert mpipe_backend.conn is None
    assert announce_started() is None
    assert mpipe_backend.conn is None


def test_stop_recv_thread_none_is_a_noop():
    """
    A lifespan that started without a supervisor (or failed before starting the
    thread) passes None to the shutdown: it must not raise.
    """
    assert stop_mpipe_recv_thread(None) is None


def test_stop_recv_thread_joins_a_finished_thread():
    """
    The shutdown waits for a receive thread that left on its own after the
    supervisor stop command, so the process does not exit over its log.
    """
    release = threading.Event()
    thread = threading.Thread(
        target=release.wait, args=(5,), name=RECV_THREAD_NAME, daemon=True
    )
    release.set()
    thread.start()

    stop_mpipe_recv_thread(thread)

    assert thread.is_alive() is False


def test_stop_recv_thread_does_not_wait_for_a_live_supervisor(monkeypatch):
    """
    With a live supervisor the thread stays blocked in the pipe read, so the
    shutdown only gives it a short grace period and returns: the daemon flag
    carries the rest, and hanging here would hold the whole process exit.
    """
    monkeypatch.setattr(lifespan_module, 'RECV_THREAD_JOIN_TIMEOUT', 0.05)

    release = threading.Event()
    thread = threading.Thread(
        target=release.wait, args=(5,), name=RECV_THREAD_NAME, daemon=True
    )
    thread.start()

    start = time.monotonic()
    stop_mpipe_recv_thread(thread)
    elapsed = time.monotonic() - start

    try:
        assert thread.is_alive() is True
        assert elapsed < 1.0
    finally:
        # let the thread end instead of leaving it blocked for the whole run
        release.set()
        thread.join(5)
