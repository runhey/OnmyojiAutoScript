"""
The slot state of the maintenance flows (``restart_base``).

The state lives in plain Python attributes written by the trio thread and read
from any thread (the rpc layer, the worker manager, the Restart topic), so these
tests pin the transitions of the slot, the context managers that hold it and the
view the frontend reads.

The flow objects are built inside the running loop: ``Flow.__init__`` creates
the ``anyio.CancelScope`` of the cancellable phase, and anyio builds a cancel
scope on the backend of the running loop only (it has no adapter for the
outside-loop case, unlike ``anyio.Lock``). In production the flows are created
by the manager entries, which run on the loop thread.
"""

import pytest

from oas.backend.app.restart.restart_base import (
    FLOW_NAMES,
    INIT_FLOW,
    STARTING_UP,
    Flow,
    FlowCancelled,
    FlowRefused,
    InitFlow,
    RestartBase,
)

pytestmark = pytest.mark.anyio


class _FakeFlow(Flow):
    """A flow of the tests: the name and the state of the base, no body"""

    name = 'restart'


class _RecordingBase(RestartBase):
    """A state that counts the view publications of its own transitions"""

    def __init__(self):
        super().__init__()
        self.published = 0

    def publish_view(self):
        self.published += 1
        super().publish_view()


async def test_module_constants_and_the_base_flow():
    assert INIT_FLOW == 'init'
    assert FLOW_NAMES == ('startup', 'restart', 'update', 'daily')
    assert 'starting up' in STARTING_UP
    assert issubclass(FlowRefused, RuntimeError)
    assert issubclass(FlowCancelled, RuntimeError)
    # the slot is entered as init and Flow.name is '' on the base only
    assert InitFlow.name == INIT_FLOW
    assert InitFlow().name == INIT_FLOW
    assert Flow.name == ''
    assert Flow.REFUSALS == {}


def test_a_free_slot_reads_as_idle():
    base = RestartBase()
    assert base.current is None
    assert base.flow_running is False
    assert base.flow_name == ''
    assert base.cancellable is False
    assert base.upgraded is False
    assert base.frozen is False
    assert base.nursery is None
    assert base.view() == {'flow': '', 'cancellable': False, 'upgraded': False}
    # the view carries exactly the three keys the frontend reads
    assert list(base.view()) == ['flow', 'cancellable', 'upgraded']


async def test_the_init_slot_reports_the_init_flow():
    base = RestartBase()
    base.claim(InitFlow())
    assert base.flow_running is True
    assert base.flow_name == INIT_FLOW
    assert base.view()['flow'] == INIT_FLOW


async def test_claim_and_release_transition():
    base = RestartBase()
    flow = _FakeFlow()
    base.claim(flow)
    assert base.current is flow
    assert base.flow_running is True
    assert base.flow_name == 'restart'
    base.release(flow)
    assert base.current is None
    assert base.flow_running is False
    # an idle release is a no-op
    base.release(flow)
    assert base.current is None


async def test_release_leaves_a_flow_it_does_not_own_alone():
    """
    Only the flow that still holds the slot releases it: the one that was taken
    over (a force restart) finds ``current`` moved on.
    """
    base = RestartBase()
    first = _FakeFlow()
    second = _FakeFlow()
    base.claim(first)
    base.claim(second)
    base.release(first)
    assert base.current is second
    base.release(second)
    assert base.current is None


async def test_claim_itself_does_not_judge_the_slot():
    """
    ``claim`` is a plain write; the judgment that refuses a second request
    (``FlowRefused``) belongs to ``RestartManager._claim``, the entries. This
    pins that division of labour instead of inventing a refusal here.
    """
    base = RestartBase()
    first = _FakeFlow()
    second = _FakeFlow()
    base.claim(first)
    base.claim(second)
    assert base.current is second


async def test_claim_and_release_publish_the_view():
    base = _RecordingBase()
    flow = _FakeFlow()
    base.claim(flow)
    assert base.published == 1
    base.release(flow)
    assert base.published == 2
    # a release that does not own the slot publishes nothing
    base.release(flow)
    assert base.published == 2


def test_publish_view_hook_is_a_no_op_on_the_base():
    """
    The base alone has nothing to publish: the topic push belongs to the step
    layer (``RestartStep.publish_view``).
    """
    base = RestartBase()
    assert base.publish_view() is None
    assert base.current is None
    assert base.frozen is False


async def test_slot_releases_on_exit():
    base = _RecordingBase()
    flow = _FakeFlow()
    with base.slot(flow) as held:
        assert held is flow
        assert base.current is flow
        assert base.flow_running is True
    assert base.current is None
    assert base.flow_running is False
    assert base.published == 2


async def test_slot_releases_when_the_body_raises():
    base = _RecordingBase()
    flow = _FakeFlow()
    with pytest.raises(ValueError, match='the body failed'):
        with base.slot(flow):
            assert base.current is flow
            raise ValueError('the body failed')
    assert base.current is None
    assert base.flow_running is False
    assert base.published == 2


async def test_slot_does_not_claim_a_flow_that_already_owns_the_slot():
    base = _RecordingBase()
    flow = _FakeFlow()
    base.claim(flow)
    assert base.published == 1
    with base.slot(flow):
        assert base.current is flow
        # the claim belongs to the request, the body does not claim again
        assert base.published == 1
    assert base.current is None
    assert base.published == 2


def test_handover_intent_keeps_the_flag_frozen_after_a_handover():
    """
    The frozen flag is never cleared in the process it was set in: from the
    publication on the process is about to be replaced, and the next process
    starts with a fresh state. Only a failed publication clears it.
    """
    base = _RecordingBase()
    assert base.frozen is False
    with base.handover_intent():
        assert base.frozen is True
    assert base.frozen is True
    assert base.published == 1


def test_handover_intent_clears_the_flag_when_the_publication_fails():
    """
    A frozen state without a handover would refuse every worker start forever,
    so the context manager clears the flag on the way out of a failure (the
    caller then withdraws the file and the backend keeps running).
    """
    base = _RecordingBase()
    with pytest.raises(RuntimeError, match='the publication failed'):
        with base.handover_intent():
            assert base.frozen is True
            raise RuntimeError('the publication failed')
    assert base.frozen is False
    assert base.published == 2


async def test_reset_returns_to_the_fresh_process_state():
    base = RestartBase()
    base.claim(_FakeFlow())
    base.frozen = True
    base.nursery = object()
    base.reset()
    assert base.current is None
    assert base.frozen is False
    assert base.nursery is None
    assert base.flow_running is False


async def test_view_follows_the_flow_in_flight():
    base = RestartBase()
    flow = _FakeFlow()
    base.claim(flow)
    assert base.view() == {'flow': 'restart', 'cancellable': False, 'upgraded': False}
    with flow.cancel_window('the handover started'):
        # the window is open: the flow may be cancelled, so is the view
        assert base.cancellable is True
        assert base.view()['cancellable'] is True
    assert base.cancellable is False
    flow.upgrade_to_daily()
    assert base.upgraded is True
    assert base.view()['upgraded'] is True
