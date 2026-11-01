"""
The FastAPI application of the backend: the lifespan that binds the loop
bridge and opens the global task group, and the app built around it.
"""

import asyncio
import contextlib

import anyio
from fastapi import FastAPI, Request
from starlette.responses import Response

from oas.backend.anyio import AnyIO
from oas.backend.auth import auth
from oas.backend.auth.errors import HTTPExceptionJson
from oas.backend.middleware.gate import DeploymentGateMiddleware
from oas.backend.ws import renew as ws_renew
from oas.backend.ws.context import GLOBAL_CONTEXT
from oas.backend.ws.renew import renewal_manager
from oas.backend.ws.ws_server import WebsocketTopicServer
from oas.logger import logger


async def task_listen_shutdown():
    """
    End the backend once the shutdown event is set.

    The event is set by whoever stops the backend: the supervisor stop
    command over mpipe, the restart / stop RPCs, or the host process going
    away. This task owns the one shutdown flow: it asks the connections to
    close (1001) and cancels the global task group, which is what makes the
    ASGI server stop.

    close_all_connections must not await: the server driven stop (lifespan's
    post-yield block) sets the event and cancels the group in the same step,
    and a pending cancellation is only delivered at a checkpoint -- an await
    inside it would let the cancel land first and leave the connections
    unasked.
    """
    await GLOBAL_CONTEXT.shutdown_event.wait()
    # the supervisor stop path must close the websockets too, before the
    # task group takes the remaining tasks down
    await WebsocketTopicServer.close_all_connections()
    GLOBAL_CONTEXT.global_task_group.cancel_scope.cancel()


async def task_gc(wait=8):
    """
    Coroutine task that do garbage collect periodically at background

    wait=8 is a magic number from Alasio: its trio working thread exits
    after 10s of idle, so wait=8 keeps the thread from starting and
    stopping every time and still leaves a free thread while gc is not
    running. Alasio hops into that thread because its gc touches the
    sqlite pool and the json cache; the only collector migrated so far
    (renewal codes) is an in-memory table taking its own lock, so OAS
    collects inline.

    Args:
        wait (int): Seconds between two gc passes
    """
    while True:
        # sleep first, no need to do gc at startup
        await anyio.sleep(wait)

        try:
            # renewal codes: expiry scan, the main cleanup hook
            renewal_manager.gc()
        except Exception as e:
            logger.error(f'task_gc error: {e}')
            logger.exception(e)


async def http_exception_json(request: Request, exc: HTTPExceptionJson) -> Response:
    """
    Render HTTPExceptionJson as the json body it already carries.

    FastAPI's default handler wraps the detail in {"detail": ...} and
    json-encodes it, which cannot take the bytes detail this exception
    carries (Alasio relied on starlette's plain-text handler passing a
    bytes detail through, which sent the json body as text/plain). The
    body stays the {"err": ..., "data": ...} the frontend translates,
    only the content type is explicitly json.

    Args:
        request (Request): The request, unused
        exc (HTTPExceptionJson): The exception raised by a router or a
            dependency

    Returns:
        Response: The json response
    """
    return Response(
        content=exc.detail,
        status_code=exc.status_code,
        headers=exc.headers,
        media_type='application/json',
    )


@contextlib.asynccontextmanager
async def lifespan(app: 'FastAPI'):
    """
    Bind the loop and open the global task group, and undo both at the end.

    FastAPI drives this generator around the whole server lifetime: what
    runs before the yield is startup, what runs after it is shutdown. The
    task group opened here owns the long-lived background tasks of the
    backend and is cancelled with everything still in it when the process
    stops, so no task can outlive the server.

    Args:
        app (FastAPI): The application, unused: the signature is FastAPI's
    """
    AnyIO.bind_loop(asyncio.get_running_loop())
    logger.info('Lifespan start')
    try:
        async with anyio.create_task_group() as task_group:
            # inject global context
            GLOBAL_CONTEXT.global_task_group = task_group
            GLOBAL_CONTEXT.shutdown_event = anyio.Event()
            # a fresh termination event per lifespan: the class attribute
            # lives as long as the process, and one left set would close
            # every connection of the next run immediately
            WebsocketTopicServer.server_terminated = anyio.Event()
            # start listening shutdown. start_soon returns a TaskHandle: never
            # await it (that would wait for the task to finish, and this one
            # only finishes at shutdown)
            task_group.start_soon(task_listen_shutdown)
            task_group.start_soon(task_gc)

            # actual backend runs here
            yield

            # the server driven stop: wake the shutdown listener, which owns
            # the one shutdown flow (close the connections, then cancel the
            # group), and cancel what is left -- a task that never ends may
            # not hold the exit
            GLOBAL_CONTEXT.shutdown_event.set()
            task_group.cancel_scope.cancel()

        logger.info('Lifespan end')
    finally:
        # the context must not keep a task group of a dead loop alive
        GLOBAL_CONTEXT.global_task_group = None
        GLOBAL_CONTEXT.shutdown_event = None
        AnyIO.unbind_loop()


def create_app() -> FastAPI:
    """
    Build the application: lifespan, the deployment gate, the api routers
    and the json error handler.

    Returns:
        FastAPI: The application, ready for uvicorn to serve
    """
    app = FastAPI(lifespan=lifespan)

    # The json error contract of the auth layer: HTTPExceptionJson carries
    # a pre-encoded {"err": ..., "data": ...} body, which FastAPI's
    # default HTTPException handler cannot render (see the handler).
    app.add_exception_handler(HTTPExceptionJson, http_exception_json)

    # Global admission + login middleware: DeploymentGateMiddleware
    # (rules A/B first: 403 / 4001, then the JWT login layer: 401).
    # The two layers are merged into one middleware with a fixed order
    # and must never be split or reordered (the login check relies on
    # rule A having run first). It is the only middleware of the app, so
    # it is the outermost layer: nothing runs before it.
    app.add_middleware(DeploymentGateMiddleware)

    # All APIs should under /api
    # Builtin APIs
    app.include_router(auth.router, prefix='/api')

    # Renewal code endpoint: POST /api/ws/renew (require_login +
    # require_local_flutter), mounted after the auth router
    app.include_router(ws_renew.router, prefix='/api')

    return app
