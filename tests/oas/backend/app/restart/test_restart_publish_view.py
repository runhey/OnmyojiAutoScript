"""
The view push of the step layer (the one deliberate deviation).

``RestartStep.publish_view`` hands the push to the loop as a coroutine --
``asyncio.run_coroutine_threadsafe(_start_view_push(nursery, step.push_view),
AnyIO.loop())`` -- instead of calling anyio's loop-thread-only and
async-context-only ``TaskGroup.start_soon`` directly, because the entry points
that reach this hook (``claim`` / ``release`` / ``cancel_window`` /
``abandon_startup``) are synchronous and, upstream, thread safe
(``trio.Nursery.start_soon``).

The ``AnyIO.call_soon`` doorbell was tried first and does not deliver that: it
schedules a plain loop callback carrying the context of the calling thread, in
which anyio cannot resolve a running async library, so ``TaskGroup.start_soon``
raised ``NoEventLoopError`` there and the push was silently dropped from a
worker thread. The regression test at the end of the module is that case.

The push is checked at two levels: with a nursery stub, which pins the call
shape deterministically, and with a real anyio task group, which is where the
semantics have to hold.
"""

import asyncio

import anyio
import pytest

from oas.backend.anyio import AnyIO
from oas.backend.app.restart.restart_step import RestartStep

pytestmark = pytest.mark.anyio


class _Nursery:
    """A nursery stub recording the task starts it is asked for"""

    def __init__(self):
        self.starts = []

    def start_soon(self, func, *args):
        self.starts.append((func, args))


def _make_step():
    """A step with stand-in collaborators (no singleton is touched)"""
    return RestartStep(
        worker_manager=object(),
        update_check=object(),
        daily=object(),
        files=object(),
    )


def test_publish_view_without_a_nursery_does_nothing():
    """The manager does not run: no flow can own the slot, there is no push"""
    step = _make_step()
    assert step.nursery is None
    assert step.publish_view() is None


async def test_publish_view_start_lands_from_a_worker_thread():
    """
    A worker-thread caller and a nursery stub: the hand-off reaches the loop,
    which asks the stub for the push task.
    """
    # the lifespan binds the loop the thread hop comes back to
    AnyIO.bind_loop(asyncio.get_running_loop())
    step = _make_step()
    nursery = _Nursery()
    step.nursery = nursery
    async with anyio.create_task_group():
        await anyio.to_thread.run_sync(step.publish_view)
        with anyio.fail_after(5):
            while not nursery.starts:
                await anyio.sleep(0.01)
    assert len(nursery.starts) == 1
    func, args = nursery.starts[0]
    # the push task itself is handed over, not run: start_soon is the call the
    # nursery gets
    assert func == step.push_view
    assert args == ()


async def test_publish_view_from_a_thread_without_a_loop_is_absorbed():
    """
    No loop is bound and the calling thread has none: ``AnyIO.loop()`` absorbs
    the push instead of raising out of a request path (the thread-safe
    ``trio.Nursery.start_soon`` it replaces would raise RunFinishedError).
    """
    AnyIO.unbind_loop()
    step = _make_step()
    nursery = _Nursery()
    step.nursery = nursery
    async with anyio.create_task_group():
        await anyio.to_thread.run_sync(step.publish_view)
        await anyio.sleep(0.05)
    assert nursery.starts == []


async def test_publish_view_from_the_loop_thread_starts_a_real_task_group_task():
    """
    The production shape works: the manager entries run on the loop thread, and
    the doorbell starts the push task in the running task group.
    """
    AnyIO.bind_loop(asyncio.get_running_loop())
    step = _make_step()
    started = []

    async def push():
        started.append(True)

    step.push_view = push
    async with anyio.create_task_group() as nursery:
        step.nursery = nursery
        step.publish_view()
        with anyio.fail_after(5):
            while not started:
                await anyio.sleep(0.01)
    assert started == [True]


async def test_publish_view_from_a_worker_thread_starts_a_real_task_group_task():
    """
    A worker-thread caller starts the push in the running task group.

    This is the case the deviation exists for, and the one the
    ``AnyIO.call_soon`` doorbell failed: a callback scheduled from a worker
    thread carries the context of that thread, in which anyio cannot resolve a
    running async library, so ``TaskGroup.start_soon`` raised
    ``NoEventLoopError`` inside the callback ("Exception in callback
    TaskGroup.start_soon()" on the loop's exception handler): the caller saw
    nothing and the view was never pushed. Upstream's thread-safe
    ``trio.Nursery.start_soon`` did start the task here; handing the start to the
    loop as a coroutine gives it the async context ``start_soon`` needs.
    """
    AnyIO.bind_loop(asyncio.get_running_loop())
    step = _make_step()
    started = []

    async def push():
        started.append(True)

    step.push_view = push
    async with anyio.create_task_group() as nursery:
        step.nursery = nursery
        await anyio.to_thread.run_sync(step.publish_view)
        with anyio.fail_after(5):
            while not started:
                await anyio.sleep(0.01)
    assert started == [True]
