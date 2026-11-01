"""
The restart / stop entries of the backend lifespan and the shutdown proxy.

``SHUTDOWN_EVENT`` in OAS is a proxy over ``GLOBAL_CONTEXT.shutdown_event`` (the
app injects the event per lifespan), so these tests drive the proxy through the
context object and stub the supervisor pipe of the module.
"""

import anyio
import pytest

from oas.backend.app import lifespan as lifespan_module
from oas.backend.app.lifespan import SHUTDOWN_EVENT, lifespan_restart, lifespan_stop
from oas.backend.ws.context import GLOBAL_CONTEXT

pytestmark = pytest.mark.anyio


class _Supervisor:
    """A supervisor pipe stub recording what the lifespan sends"""

    def __init__(self):
        self.sent = []

    def send(self, data, strict=False):
        self.sent.append((data, strict))


@pytest.fixture
def supervisor(monkeypatch):
    """The lifespan module sees an attached supervisor pipe"""
    supervisor = _Supervisor()
    monkeypatch.setattr(lifespan_module, 'mpipe_backend', supervisor)
    return supervisor


@pytest.fixture
def no_supervisor(monkeypatch):
    """The lifespan module sees no supervisor pipe"""
    monkeypatch.setattr(lifespan_module, 'mpipe_backend', None)
    return None


@pytest.fixture
def shutdown_event(monkeypatch):
    """A running lifespan: the proxy has an event to forward to"""
    event = anyio.Event()
    monkeypatch.setattr(GLOBAL_CONTEXT, 'shutdown_event', event)
    return event


async def test_is_set_is_false_without_a_lifespan_event():
    assert GLOBAL_CONTEXT.shutdown_event is None
    assert SHUTDOWN_EVENT.is_set() is False


def test_set_without_a_lifespan_event_logs_and_does_not_raise():
    """
    The proxy never falls back to an event of its own: a maintenance flow
    signalling a backend that is not running must not look like it succeeded.
    """
    assert GLOBAL_CONTEXT.shutdown_event is None
    assert SHUTDOWN_EVENT.set() is None
    assert SHUTDOWN_EVENT.is_set() is False


async def test_wait_without_a_lifespan_event_returns():
    assert GLOBAL_CONTEXT.shutdown_event is None
    with anyio.fail_after(5):
        await SHUTDOWN_EVENT.wait()


async def test_the_proxy_forwards_to_the_lifespan_event(shutdown_event):
    assert GLOBAL_CONTEXT.shutdown_event is shutdown_event
    assert SHUTDOWN_EVENT.is_set() is False
    SHUTDOWN_EVENT.set()
    assert shutdown_event.is_set() is True
    assert SHUTDOWN_EVENT.is_set() is True
    with anyio.fail_after(5):
        await SHUTDOWN_EVENT.wait()


async def test_lifespan_restart_without_a_supervisor_raises(no_supervisor):
    with pytest.raises(PermissionError, match='without supervisor'):
        await lifespan_restart()


async def test_lifespan_stop_without_a_supervisor_raises(no_supervisor):
    with pytest.raises(PermissionError, match='without supervisor'):
        await lifespan_stop()


async def test_lifespan_restart_sends_the_command_and_signals_the_shutdown(
    supervisor, shutdown_event
):
    await lifespan_restart()
    # the strict flag must fail loudly when the pipe is unavailable
    assert supervisor.sent == [(b'command:restart', True)]
    assert shutdown_event.is_set() is True
    assert SHUTDOWN_EVENT.is_set() is True


async def test_lifespan_stop_sends_the_command_and_signals_the_shutdown(
    supervisor, shutdown_event
):
    await lifespan_stop()
    assert supervisor.sent == [(b'command:stop', True)]
    assert shutdown_event.is_set() is True
    assert SHUTDOWN_EVENT.is_set() is True
