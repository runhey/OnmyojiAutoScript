"""
The entries of the restart manager: which request is refused, and why.

None of these tests runs a flow: they claim the slot by hand or hand it to the
manager without a nursery (``run()`` owns the nursery and serves the flows),
which is exactly the window the entries judge. A refusal is cheap and
synchronous -- no flow body, no task, no collaborator is reached.
"""

import builtins
import inspect

import pytest

from oas.backend.app.restart import restart_manager as restart_manager_module
from oas.backend.app.restart.restart_base import (
    INIT_FLOW,
    FlowRefused,
    InitFlow,
)
from oas.backend.app.restart.restart_flow import FlowRestart
from oas.backend.app.restart.restart_manager import RESTART_MANAGER, RestartManager
from oas.backend.mpipe.mpipe_backend import has_supervisor

pytestmark = pytest.mark.anyio


@pytest.fixture
def manager():
    """A manager of this test, not the process singleton"""
    return RestartManager()


@pytest.fixture
def no_supervisor(monkeypatch):
    """The backend of the test process runs without a supervisor pipe"""
    monkeypatch.setattr(builtins, '__mpipe_conn__', None, raising=False)
    return None


@pytest.fixture
def supervisor(monkeypatch):
    """A supervisor pipe is attached (nothing is sent through it here)"""
    monkeypatch.setattr(builtins, '__mpipe_conn__', object(), raising=False)
    return None


def test_process_singleton_is_readable_and_has_the_entries():
    assert isinstance(RESTART_MANAGER, RestartManager)
    # the two members the worker manager reads
    assert RESTART_MANAGER.frozen is False
    assert RESTART_MANAGER.flow_running is False
    assert RESTART_MANAGER.flow_name == ''
    assert inspect.iscoroutinefunction(RESTART_MANAGER.force_restart)
    assert inspect.iscoroutinefunction(RESTART_MANAGER.abort)
    assert inspect.iscoroutinefunction(RESTART_MANAGER.cancel_restart)
    assert inspect.iscoroutinefunction(RESTART_MANAGER.cancel_apply)
    assert callable(RESTART_MANAGER.restart)
    assert callable(RESTART_MANAGER.update_apply)
    assert callable(RESTART_MANAGER.request_startup)
    assert callable(RESTART_MANAGER.request_daily)


def test_flow_refused_is_reexported():
    assert restart_manager_module.FlowRefused is FlowRefused


def test_restart_without_a_supervisor_is_refused(manager, no_supervisor):
    """
    Only a supervisor spawns the new process: refusing up front is the accurate
    answer instead of failing at the handover.
    """
    assert has_supervisor() is False
    with pytest.raises(FlowRefused, match='without a supervisor'):
        manager.restart()
    # the request was refused, nothing was claimed
    assert manager.flow_running is False


def test_a_user_entry_without_a_run_is_refused_as_starting_up(manager, supervisor):
    """
    A supervisor is attached but the manager does not serve flows yet (``run()``
    did not run, the slot is free): the user entry answers like any startup
    window instead of spawning a task.
    """
    with pytest.raises(FlowRefused, match='starting up'):
        manager.restart()
    assert manager.flow_running is False


async def test_a_user_entry_landing_on_the_init_slot_is_refused(manager):
    """
    The only transition out of init is the startup flow: a user flow claimed
    there would refuse the startup and leave the process without its checks.
    """
    manager.claim(InitFlow())
    with pytest.raises(FlowRefused, match='starting up'):
        manager.update_apply()
    assert manager.flow_name == INIT_FLOW


async def test_a_second_claim_is_refused_with_the_refusal_of_the_request(manager):
    """
    A restart owns the backend: the update entry answers with its own
    user-facing reason (``FlowUpdate.REFUSALS``), not with a generic error.
    """
    manager.claim(FlowRestart(manager))
    with pytest.raises(FlowRefused, match='A restart is in progress'):
        manager.update_apply()
    # the refusal leaves the slot alone
    assert manager.flow_name == 'restart'


async def test_enter_init_claims_the_slot_once(manager):
    assert manager.flow_running is False
    manager.enter_init()
    assert manager.flow_name == INIT_FLOW
    init = manager.current
    manager.enter_init()
    assert manager.current is init


def test_request_daily_waits_for_the_startup_flow(manager):
    """
    The daily action is a *due* decision: before the startup flow claimed the
    slot nothing may be claimed, the next evaluation retries.
    """
    assert manager.nursery is None
    assert manager.request_daily() is None
    assert manager.flow_running is False


def test_spawn_without_a_run_raises(manager):
    """
    The nursery is the manager's own: a task can only be spawned while ``run()``
    serves it.
    """
    assert manager.nursery is None
    with pytest.raises(RuntimeError, match='does not run'):
        manager.spawn(object())
