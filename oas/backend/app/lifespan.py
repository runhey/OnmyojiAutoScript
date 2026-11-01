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

The rest of the upstream module (``mpipe_recv_loop``, ``notify_rotation``,
``announce_started``, ``get_shutdown_trigger``, and the host stdin commands
``set_lang`` / ``set_theme`` / ``set_dpi_scaling`` which need upstream's
``alasio/backend/app/prefs.py``) is deliberately not ported yet: it belongs to
the mpipe lifespan item of ``oas/backend/README.md`` (leftover 6), which also
has to move OAS's uvicorn startup onto the supervisor handover.
"""

import anyio

from oas.backend.mpipe.mpipe_backend import mpipe_backend
from oas.backend.ws.context import GLOBAL_CONTEXT
from oas.logger import logger


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
