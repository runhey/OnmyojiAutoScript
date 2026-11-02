"""
The pieces of the upstream backend lifespan that the maintenance flows need.

Ported from ``alasio/backend/app/lifespan.py``, selectively: only
``SHUTDOWN_EVENT``, ``lifespan_restart`` and ``lifespan_stop`` live here,
because they are the only three names the ported restart package imports
(``oas/backend/app/restart/restart_step.py`` calls ``SHUTDOWN_EVENT.is_set()``
and defaults its ``restart_fn`` to ``lifespan_restart``).

Deviation 1 -- ``SHUTDOWN_EVENT``. Upstream owns a module-level
``SHUTDOWN_EVENT = trio.Event()`` and its ASGI layer starts a second thread
(``mpipe_recv_loop``) that sets it. OAS serves the app with uvicorn on asyncio
and already owns exactly one shutdown event, created per lifespan in
``oas/backend/app/app.py`` and published as ``GLOBAL_CONTEXT.shutdown_event``,
so ``SHUTDOWN_EVENT`` here is a proxy object that reads that event instead:
``set()`` / ``is_set()`` / ``await wait()`` forward to it. When no lifespan
event exists (the app was never started, or it already shut down) the call is
logged and swallowed -- the proxy never falls back to an event of its own,
because a maintenance flow signalling a backend that is not running must not
look like it succeeded.

Deviation 2 -- ``trio.to_thread.run_sync`` became ``anyio.to_thread.run_sync``.

Deviation 3 -- the receive loop carries no trio token. Alasio threads
``trio.lowlevel.current_trio_token()`` into ``mpipe_recv_loop`` because a
thread needs it to reach the loop; OAS's ``oas.backend.anyio.AnyIO`` holds the
bound loop instead, so the token has no counterpart. The two hand-offs map as
follows: upstream ``trio.from_thread.run_sync(SHUTDOWN_EVENT.set, ...)``
becomes ``AnyIO.call_soon(SHUTDOWN_EVENT.set)`` -- a plain sync callback, which
is exactly what ``Event.set`` in the loop's ready queue needs -- and upstream
``trio.from_thread.run(...)`` (abort the maintenance flow, notify the
connections) becomes ``asyncio.run_coroutine_threadsafe(...)``, because a
coroutine needs a task context a loop callback does not have. Both of those
futures are waited on: upstream's ``from_thread.run`` blocks and re-raises the
coroutine's exception into the calling thread, and dropping the future would
lose an abort failure from the log.

Deviation 4 -- ``trio.fail_after`` became ``anyio.fail_after``,
``trio.TooSlowError`` became ``TimeoutError``, and the concurrent rotation
notification runs in an ``anyio`` task group.

Deviation 5 -- names: upstream's ``REQUIRE_ELECTRON`` is OAS's
``REQUIRE_LOCAL_FLUTTER`` (``oas/backend/ws/ws_topic.py:29``, the same
subscription-time restriction) and the connection attribute is ``local_token``
(``oas/backend/ws/ws_server.py:174``) instead of ``auth_token``.

Deviation 6 -- the host stdin commands (``command:set_lang:``,
``command:set_theme:``, ``command:set_dpi_scaling:``) are not ported: they need
upstream's ``alasio/backend/app/prefs.py``. They fall through to upstream's
unknown-message warning until that module lands.

Deviation 7 -- upstream starts the receive thread inside
``get_shutdown_trigger``, whose returned trigger hypercorn takes as its
shutdown hook. uvicorn takes no such hook, and OAS's shutdown listener
(``task_listen_shutdown`` in ``app/app.py``) already waits on the event the
thread sets, so only the thread half is kept: ``start_mpipe_recv_thread`` /
``stop_mpipe_recv_thread``, owned by the lifespan.

Porting note: the caller of ``announce_started`` used to be missing, and the
reason it cannot live here stands: uvicorn 0.38 runs the lifespan startup BEFORE
it binds the sockets (``uvicorn/server.py``, ``Server.startup``), so announcing
from the lifespan would confirm startup before a bind failure can happen --
exactly the window upstream keeps the supervisor in (its comment: a bind failure
must stay a startup failure instead of a restart loop). It is now called from
``BackendServer.startup`` in ``oas/backend/app/asgi.py``, right after uvicorn
created and bound the listeners.
"""

import asyncio
from threading import Thread

import anyio

from oas.backend.anyio import AnyIO
from oas.backend.mpipe.mpipe_backend import mpipe_backend
from oas.backend.mpipe.token_backend import token_table
from oas.backend.reactive.event import ResponseEvent
from oas.backend.ws.context import GLOBAL_CONTEXT
from oas.backend.ws.ws_server import WebsocketTopicServer
from oas.logger import logger

# Per-connection timeout for the rotation notification (send / close):
# a stuck connection must not stall the others. notify_rotation runs
# the connections concurrently, so the whole pass is bounded by the
# slowest single connection (worst case one timeout).
ROTATION_NOTIFY_TIMEOUT = 2.0

# How long the shutdown waits for the receive thread to leave on its own. It
# only does when the supervisor is already gone or asked the backend to stop;
# a live supervisor leaves it blocked in the pipe read. Upstream never joins
# (the thread is a daemon); OAS joins for a short grace period so a
# supervisor-driven stop can finish its log, then lets the daemon die.
RECV_THREAD_JOIN_TIMEOUT = 1.0


class _ShutdownEventProxy:
    """
    Upstream's module-level ``SHUTDOWN_EVENT``, backed by the running lifespan

    Upstream can afford a module-level ``trio.Event`` because its ASGI layer
    owns the one event for the whole process. OAS creates the event per
    lifespan (``oas/backend/app/app.py``), so this reads the current one from
    ``GLOBAL_CONTEXT`` on every call instead of caching a stale object.
    """

    @property
    def event(self):
        """
        The shutdown event of the running lifespan, or None

        Returns:
            Optional[Event]: ``GLOBAL_CONTEXT.shutdown_event``
        """
        return GLOBAL_CONTEXT.shutdown_event

    def set(self):
        """
        Wake the backend shutdown listener, as upstream ``SHUTDOWN_EVENT.set()``

        Runs on the loop (the restart / stop RPCs call it there). A foreign
        thread must not call it directly: the event belongs to the loop, so it
        goes through ``AnyIO.call_soon(SHUTDOWN_EVENT.set)``, which is the
        mapping of upstream ``trio.from_thread.run_sync``.
        """
        event = self.event
        if event is None:
            logger.warning('Cannot signal backend shutdown, no lifespan shutdown event')
            return
        event.set()

    def is_set(self) -> bool:
        """
        Whether the backend shutdown was already requested

        Returns:
            bool: True when the lifespan shutdown event is set
        """
        event = self.event
        return bool(event is not None and event.is_set())

    async def wait(self):
        """
        Block until the backend shutdown was requested, as upstream
        ``await SHUTDOWN_EVENT.wait()``
        """
        event = self.event
        if event is None:
            logger.warning(
                'Cannot wait for backend shutdown, no lifespan shutdown event'
            )
            return
        await event.wait()


SHUTDOWN_EVENT = _ShutdownEventProxy()


def mpipe_recv_loop(conn):
    """
    Receive loop of the supervisor channel, running on the mpipe thread.

    Every branch hands its work back to the loop: the shutdown signal is a
    sync callback (``AnyIO.call_soon``), the two async ones -- aborting the
    maintenance flow, notifying the ws connections -- go over as coroutines.

    Args:
        conn (PipeConnection): The supervisor pipe, ``mpipe_backend.conn``
    """

    def request_shutdown(reason):
        """
        Request the backend to shut itself down.

        The shutdown event is always requested, even if logging fails: when
        the supervisor or the host process (electron) died, the stdout pipe
        may be broken and the logger could raise. The backend must never be
        left running as an orphan just because the log message could not be
        written.

        Args:
            reason (str): Log message for the shutdown
        """
        # a maintenance flow in progress (or a resume queue of the previous
        # one) is aborted: the backend is going down, nothing may restart it or
        # resume the workers afterwards. Local import: the restart package
        # imports this module (lifespan_restart), a module level import would
        # be circular. The coroutine form is the hand-off AnyIO documents for
        # work that needs an async context: abort awaits the worker thread
        # pool, so drive it from this (mpipe recv) thread through the loop.
        try:
            from oas.backend.app.restart.restart_manager import RESTART_MANAGER

            # The loop is looked up before the coroutine is made: one built
            # ahead of a failing lookup would be left un-awaited (and warned
            # about) with nowhere to run. The future is then waited on --
            # upstream trio.from_thread.run blocks until the coroutine is done
            # and re-raises its exception into this thread, so an abort that
            # fails inside the loop must reach the logger below instead of dying
            # silently in a discarded future.
            loop = AnyIO.loop()
            future = asyncio.run_coroutine_threadsafe(RESTART_MANAGER.abort(), loop)
            future.result()
        except Exception as e:
            logger.error(f'Failed to abort the maintenance flow: {e}')
        # Event.set() is the plain sync callback AnyIO.call_soon is documented
        # for; calling it from this thread directly would touch an anyio event
        # that belongs to the loop.
        AnyIO.call_soon(SHUTDOWN_EVENT.set)
        try:
            logger.info(reason)
        except Exception:
            # stdout pipe broken (host process died), drop the message
            pass

    while 1:
        try:
            msg = conn.recv_bytes()
        except EOFError, OSError:
            request_shutdown(
                'Backend disconnected to supervisor, shutting down backend'
            )
            # no live supervisor is behind this backend any more: the maintenance
            # gates (has_supervisor) must answer no while the process shuts down
            mpipe_backend.disconnect()
            break

        if msg == b'command:stop':
            request_shutdown(
                'Backend received stop request from supervisor, shutting down backend'
            )
            # a supervisor that asked the backend to stop cannot complete a restart
            # or an update for it any more: the same gates close
            mpipe_backend.disconnect()
            break
        elif msg.startswith(b'token:'):
            # New token from the supervisor rotation: add it to the table
            # (handle_token acknowledges back through MPipeBackend) and
            # notify the ws connections that hold a local token.
            token = msg[6:].decode()
            token_table.handle_token(token)
            _notify_rotation()
        else:
            # the three host stdin commands (set_lang / set_theme /
            # set_dpi_scaling) are not ported yet, see the module docstring
            logger.warning(f'Backend received unknown msg from supervisor: {msg}')


async def _notify_one(server):
    """
    Notify one restricted-subscription connection after a token rotation,
    with a per-connection timeout: a stuck or broken connection is
    skipped without affecting the other connections.

    Args:
        server (WebsocketTopicServer): The connection to notify
    """
    try:
        with anyio.fail_after(ROTATION_NOTIFY_TIMEOUT):
            if token_table.verify(server.local_token):
                # token still in the window: ask the frontend to renew
                await server.send(ResponseEvent(t='auth', o='full', v='renew'))
            else:
                # token already evicted: standard reconnect will carry a
                # fresh token on the next handshake
                await server.close(4002, 'token rotated')
    except TimeoutError:
        # send/close stuck (e.g. send buffer back-pressure), skip this
        # connection; the next rotation re-checks it
        logger.warning(f'Rotation notify timeout for {server}')
    except Exception as e:
        # a single broken connection must not abort the notification
        # of the other connections
        logger.warning(f'Rotation notify failed for {server}: {e}')


async def notify_rotation():
    """
    Notify ws connections after a token rotation: connections subscribed
    to a local-Flutter-restricted topic either receive the "renew" control
    message (token still in window) or close(4002) (token already
    evicted). Connections are notified concurrently inside a task group,
    each with its own timeout, so one stuck connection cannot stall the
    others. Runs on the loop (mpipe_recv_loop calls it through
    _notify_rotation).
    """
    targets = []
    for server in list(WebsocketTopicServer.active.values()):
        # the restricted set comes from the connection's own class
        # (subclasses register their own ALL_TOPIC_CLASS)
        restricted = {
            name
            for name, cls in type(server).ALL_TOPIC_CLASS.items()
            if cls.REQUIRE_LOCAL_FLUTTER
        }
        if not restricted.intersection(server.subscribed):
            # ordinary connections without restricted subscriptions
            # never need to renew
            continue
        targets.append(server)

    if not targets:
        return
    async with anyio.create_task_group() as task_group:
        for server in targets:
            task_group.start_soon(_notify_one, server)


def _notify_rotation():
    """
    Bridge notify_rotation into the loop from the mpipe recv thread.
    """
    try:
        # loop first (see request_shutdown), then wait for the pass the way
        # upstream trio.from_thread.run does; a failure of the pass itself is
        # swallowed here exactly like upstream swallows it
        loop = AnyIO.loop()
        future = asyncio.run_coroutine_threadsafe(notify_rotation(), loop)
        future.result()
    except Exception:
        # loop already gone, nothing to notify
        pass


def announce_started():
    """
    Announce pipe readiness to the supervisor once the listeners are bound.

    recv_loop treats the first backend message as the startup confirmation
    and only then starts the stdin listener (the listener must stay stopped
    while a backend spawns, see the Windows constraint in supervisor.py).
    Without this message the confirmation falls back to the startup_timeout
    (5s), during which a command:stop written to stdin (e.g. closing the
    webapp right after it opened) would sit unread until the timeout ends,
    longer than the Electron close flow waits before force-killing the tree.

    Called by BackendConfig.create_sockets in asgi.py right after the
    sockets are bound, before any request can arrive. A bind failure (port
    already in use) raises before this runs, so it stays a startup failure
    and the supervisor does not restart-loop on it. OAS has no such hook yet,
    see the module docstring.
    """
    mpipe_backend.send(b'command:started')


def start_mpipe_recv_thread():
    """
    Start the mpipe receive thread, or nothing when running without supervisor.

    The OAS half of upstream's ``get_shutdown_trigger``: hypercorn takes the
    returned trigger as the hook that stops it serving, uvicorn takes none
    (the shutdown listener of the lifespan already waits on the event this
    thread sets), so only the thread start is kept.

    Returns:
        Thread | None: The daemon thread, or None when no supervisor spawned
            this backend -- upstream logs the same two lines and returns None
    """
    if not mpipe_backend:
        # no supervisor, cannot restart
        logger.info('Backend running without supervisor')
        return None

    logger.info('Backend running with supervisor')
    thread = Thread(
        target=mpipe_recv_loop,
        args=(mpipe_backend.conn,),
        name='mpipe_child_recv',
        daemon=True,
    )
    thread.start()
    return thread


def stop_mpipe_recv_thread(thread):
    """
    Give the receive thread a short grace period to leave, then let it die.

    The thread only ends on its own when the supervisor is gone or asked the
    backend to stop (EOF / ``command:stop``); with a live supervisor it stays
    blocked in the pipe read, so this join can only time out. The thread is a
    daemon: a timed-out join never holds the exit.

    Args:
        thread (Thread | None): The thread returned by start_mpipe_recv_thread
    """
    if thread is None:
        return
    thread.join(RECV_THREAD_JOIN_TIMEOUT)


async def lifespan_restart():
    """
    Restart the entire backend

    Upstream body, verbatim except for the thread hop:
    ``trio.to_thread.run_sync`` -> ``anyio.to_thread.run_sync``, and the
    shutdown signal goes through the lifespan proxy above.
    """
    if not mpipe_backend:
        raise PermissionError(f'Cannot restart backend running without supervisor')

    # log
    logger.info('Backend received restart request from RPC, shutting down backend')

    # Send b'command:restart' to supervisor (strict: must fail loudly
    # when the pipe is unavailable)
    await anyio.to_thread.run_sync(mpipe_backend.send, b'command:restart', True)

    # stop backend
    SHUTDOWN_EVENT.set()


async def lifespan_stop():
    """
    Stop the entire backend

    Upstream body, with the same two deviations as ``lifespan_restart``.
    """
    if not mpipe_backend:
        raise PermissionError(f'Cannot stop backend running without supervisor')

    # log
    logger.info('Backend received stop request from RPC, shutting down backend')

    # Send b'command:stop' to supervisor (strict: must fail loudly
    # when the pipe is unavailable)
    await anyio.to_thread.run_sync(mpipe_backend.send, b'command:stop', True)

    # stop backend
    SHUTDOWN_EVENT.set()
