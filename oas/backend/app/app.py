"""
The FastAPI application of the backend: the lifespan that binds the loop
bridge and opens the global task group, and the app built around it.
"""

import asyncio
import contextlib

import anyio
from fastapi import FastAPI

from oas.backend.anyio import AnyIO
from oas.backend.ws.context import GLOBAL_CONTEXT
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
    Build the application with the backend lifespan attached.

    Returns:
        FastAPI: The application, ready for uvicorn to serve
    """
    return FastAPI(lifespan=lifespan)
