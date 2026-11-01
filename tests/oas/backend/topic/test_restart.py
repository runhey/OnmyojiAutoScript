"""
Unit tests of the Restart topic.

The topic is passive by design: it has no RPC and no producer of its own, the
restart manager pushes phases into RestartSource and the frontend reads them.
Only the source protocol (phase strings, the flow view dict, self-clearing)
is testable until that manager exists.
"""

import pytest

from oas.backend.reactive.event import ResponseEvent
from oas.backend.topic.restart import Restart, RestartSource

pytestmark = pytest.mark.anyio

CONN_ID = 'test-conn'


@pytest.fixture(autouse=True)
def clear_source():
    """RestartSource is a resident singleton: drop it around each test."""
    RestartSource.singleton_clear()
    yield
    RestartSource.singleton_clear()
    Restart.singleton_remove(CONN_ID)


def test_topic_name():
    assert Restart.TOPIC_NAME == 'Restart'
    assert Restart.rpc_methods == {}


def test_apply_sets_and_clears_the_phase():
    source = RestartSource()
    assert source._apply('stopping') is True
    assert source.data['phase'] == 'stopping'
    assert 'update' in source.data
    # a repeated phase string keeps the phase and refreshes the "update"
    # stamp, so an in-progress flow always looks alive to the frontend
    assert source._apply('stopping') is True
    assert source.data['phase'] == 'stopping'
    # an empty string clears the phase, and with no flow left the data clears
    assert source._apply('') is True
    assert source.data == {}


def test_apply_merges_the_flow_view():
    """
    A dict is a flow view patch: only the keys it carries are merged, so the
    phase survives an incoming {'flow': ...}.
    """
    source = RestartSource()
    source._apply('resuming')
    assert (
        source._apply({'flow': 'restart', 'cancellable': True, 'upgraded': False})
        is True
    )
    assert source.data['phase'] == 'resuming'
    assert source.data['flow'] == 'restart'
    assert source.data['cancellable'] is True
    assert source.data['upgraded'] is False
    # a later patch only touches its own keys
    assert source._apply({'cancellable': False}) is True
    assert source.data['cancellable'] is False
    assert source.data['flow'] == 'restart'


def test_apply_clears_the_data_when_the_flow_ends():
    source = RestartSource()
    source._apply('stopping')
    source._apply({'flow': 'update'})
    assert source._apply('') is True
    assert 'phase' not in source.data
    assert source.data['flow'] == 'update'
    assert source._apply({'flow': ''}) is True
    assert source.data == {}
    # already empty: nothing changed
    assert source._apply({'flow': ''}) is False


def test_convert_wraps_the_data_as_a_full():
    source = RestartSource()
    source._apply('stopping')
    event = source._convert(None)
    assert isinstance(event, ResponseEvent)
    assert event.t == 'Restart'
    assert event.o == 'full'
    assert event.v['phase'] == 'stopping'


async def test_restart_topic_resolves_the_source():
    """No full-data source to refresh: the topic just hands the resident one out."""
    topic = Restart(CONN_ID, None)
    assert isinstance(await topic.get_source(), RestartSource)
