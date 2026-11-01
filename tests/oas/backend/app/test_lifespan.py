"""
Lifespan tests: the app skeleton binds the loop bridge, opens one task group
for the long-lived background tasks and undoes both on shutdown.
"""

import asyncio
import threading

import anyio
from starlette.testclient import TestClient

from oas.backend.anyio import AnyIO
from oas.backend.app.app import create_app, lifespan
from oas.backend.ws.context import GLOBAL_CONTEXT


def test_app_serves_requests():
    """
    The skeleton is a real ASGI application: it answers HTTP requests.
    """
    with TestClient(create_app()) as client:
        # no route is mounted yet, the framework answers 404
        assert client.get('/').status_code == 404


def test_lifespan_binds_and_unbinds_the_loop():
    """
    The bridge holds the running loop while the app lives, and releases it
    when the app stops.
    """
    app = create_app()
    assert AnyIO._loop is None
    with TestClient(app):
        loop = AnyIO.loop()
        assert not loop.is_closed()
        assert AnyIO.call_soon(lambda: None) is True
    assert AnyIO._loop is None
    # a late push after shutdown is absorbed instead of raising
    assert AnyIO.call_soon(lambda: None) is False


def test_lifespan_injects_and_clears_the_global_context():
    """
    The lifespan injects the global task group and the shutdown event, and
    clears both when it ends.
    """
    app = create_app()
    with TestClient(app):
        assert GLOBAL_CONTEXT.global_task_group is not None
        assert GLOBAL_CONTEXT.shutdown_event is not None
        assert not GLOBAL_CONTEXT.shutdown_event.is_set()
    assert GLOBAL_CONTEXT.global_task_group is None
    assert GLOBAL_CONTEXT.shutdown_event is None


def test_shutdown_event_is_set_on_the_way_out():
    """
    A server driven shutdown sets the event too, so everything waiting on it
    can stop before the task group is cancelled.
    """
    app = create_app()
    with TestClient(app):
        event = GLOBAL_CONTEXT.shutdown_event
    assert event.is_set()


def test_global_task_group_cancels_its_tasks_on_shutdown():
    """
    A background task started on the global task group is cancelled when the
    lifespan ends.
    """
    started = threading.Event()
    stopped = threading.Event()

    async def background():
        started.set()
        try:
            await anyio.sleep_forever()
        finally:
            stopped.set()

    async def start_background():
        GLOBAL_CONTEXT.global_task_group.start_soon(background)

    with TestClient(create_app()):
        # the test thread runs no loop: hand the start to the loop of the app.
        # start_soon needs an async task context, which a bare loop callback
        # does not have, so it goes over as a coroutine.
        future = asyncio.run_coroutine_threadsafe(start_background(), AnyIO.loop())
        future.result(timeout=5)
        assert started.wait(timeout=5) is True
    assert stopped.wait(timeout=5) is True


def test_shutdown_event_stops_the_backend():
    """
    Setting the shutdown event - what the supervisor stop command and the
    restart / stop RPCs do - tears the lifespan down.
    """

    async def main():
        app = create_app()
        started = anyio.Event()
        stopped = []

        async def background():
            started.set()
            try:
                await anyio.sleep_forever()
            finally:
                stopped.append(True)

        async with lifespan(app):
            GLOBAL_CONTEXT.global_task_group.start_soon(background)
            await started.wait()
            GLOBAL_CONTEXT.shutdown_event.set()

        assert stopped == [True]
        assert GLOBAL_CONTEXT.global_task_group is None
        assert GLOBAL_CONTEXT.shutdown_event is None
        assert AnyIO._loop is None

    anyio.run(main)
