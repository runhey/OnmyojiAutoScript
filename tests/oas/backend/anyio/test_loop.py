"""
Tests for the backend loop bridge (oas/backend/anyio/loop.py): the
replacement of Trio's TrioToken / run_sync_soon / RunFinishedError.

These are sync tests driving anyio.run() directly, because the two
properties under test -- lazy loop capture and "the loop is gone" -- are
about the boundary between the loop and the threads outside it.
"""

import asyncio
import threading

import anyio
import pytest

from oas.backend.anyio import AnyIO


@pytest.fixture(autouse=True)
def clean_bridge():
    """Every test starts with no loop bound (as at process start)"""
    AnyIO.unbind_loop()
    yield
    AnyIO.unbind_loop()


def test_call_soon_reaches_the_loop_from_a_plain_thread():
    """A worker thread hands a callback to the loop, run_sync_soon style"""
    sent = []
    scheduled = []
    done = threading.Event()

    async def main():
        AnyIO.bind_loop(asyncio.get_running_loop())

        def producer():
            try:
                scheduled.append(AnyIO.call_soon(sent.append, 'from-thread'))
            finally:
                done.set()

        threading.Thread(target=producer).start()
        with anyio.move_on_after(5):
            while not done.is_set():
                await anyio.sleep(0.001)
        # let the queued callback run
        await anyio.sleep(0.01)
        return list(sent)

    assert anyio.run(main) == ['from-thread']
    assert scheduled == [True]


def test_call_soon_defers_even_on_the_loop_thread():
    """
    The callback is queued, never run inline -- source.reinit queues a full
    event from the loop thread and depends on running behind it.
    """

    async def main():
        AnyIO.bind_loop(asyncio.get_running_loop())
        order = []
        order.append('before')
        AnyIO.call_soon(order.append, 'scheduled')
        order.append('after')
        await anyio.sleep(0)
        return order

    assert anyio.run(main) == ['before', 'after', 'scheduled']


def test_call_soon_without_a_loop_reports_failure():
    """Unbound and called off-loop: nothing to ring, no exception"""
    assert AnyIO.call_soon(lambda: None) is False


def test_loop_captures_the_running_loop_when_unbound():
    """No lifespan: loop() registers the calling loop on the fly"""
    captured = []

    async def main():
        AnyIO.unbind_loop()
        captured.append(AnyIO.loop() is asyncio.get_running_loop())
        return AnyIO.loop()

    loop = anyio.run(main)
    assert captured == [True]
    assert loop.is_closed()


def test_call_soon_after_the_loop_closed_is_absorbed():
    """
    The replacement of `except trio.RunFinishedError: pass`: a thread
    pushing after shutdown reports failure instead of raising.
    """

    async def main():
        AnyIO.bind_loop(asyncio.get_running_loop())

    anyio.run(main)
    # the loop of that run is gone; a late worker-thread push must not raise
    assert AnyIO.call_soon(lambda: None) is False


def test_call_soon_reraises_any_other_runtime_error(monkeypatch):
    """
    Only the closed loop is absorbed: a RuntimeError that is not the
    shutdown must surface instead of being mistaken for one.
    """

    class FakeLoop:
        def is_closed(self):
            return False

        def call_soon_threadsafe(self, *args):
            raise RuntimeError('loop is on fire')

    monkeypatch.setattr(AnyIO, '_loop', FakeLoop())
    with pytest.raises(RuntimeError, match='loop is on fire'):
        AnyIO.call_soon(lambda: None)


def test_a_bare_callback_has_no_async_task_context():
    """
    The callback runs as a plain loop callback: the loop thread, but no
    async task context. What the reactive drain and the ws outbox need does
    work there (sync work, Event.set(), send_nowait()); start_soon() and
    cancel scopes do not, and go over as a coroutine instead.
    """
    outcome = {}
    done = threading.Event()

    async def main():
        AnyIO.bind_loop(asyncio.get_running_loop())
        event = anyio.Event()
        send, _receive = anyio.create_memory_object_stream(1)

        def callback():
            def probe(name, call):
                try:
                    call()
                    outcome[name] = 'ok'
                except BaseException as exc:
                    outcome[name] = type(exc).__name__

            probe('event_set', event.set)
            probe('send_nowait', lambda: send.send_nowait(b'x'))
            probe('cancel_scope', anyio.CancelScope)
            probe('cancelled_class', anyio.get_cancelled_exc_class)
            done.set()

        threading.Thread(target=lambda: AnyIO.call_soon(callback)).start()
        with anyio.move_on_after(5):
            while not done.is_set():
                await anyio.sleep(0.001)

    anyio.run(main)
    assert outcome == {
        'event_set': 'ok',
        'send_nowait': 'ok',
        'cancel_scope': 'NoEventLoopError',
        'cancelled_class': 'NoEventLoopError',
    }
