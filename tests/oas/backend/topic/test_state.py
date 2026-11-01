"""
Unit tests of the ConnState topic: the state struct and the RPC contract.

The connection-level behavior (registered without subscribing, the language
negotiated from cookie and header, the RPCs over the wire) is covered end to
end by tests/oas/backend/ws/test_ws_conn_state.py.
"""

import pytest

from oas.backend.reactive.event import RpcValueError
from oas.backend.topic.state import ConnState, NavState

pytestmark = pytest.mark.anyio

CONN_ID = 'test-conn'


@pytest.fixture
def topic():
    """
    One ConnState with no server behind it.

    These RPCs never touch the connection (no source, no send), so the topic
    only needs its own state; the instance is dropped from the singleton
    afterwards.
    """
    yield ConnState(CONN_ID, None)
    ConnState.singleton_remove(CONN_ID)


def current_state(topic) -> NavState:
    """
    The NavState of a topic, read the way the reactive stores it.

    Args:
        topic (ConnState): The topic to read

    Returns:
        NavState: The cached state (None when never computed)
    """
    return getattr(topic, '_reactive_cache_nav_state', None)


def test_nav_state_defaults():
    state = NavState()
    assert state.lang == 'en-US'
    assert (state.config_name, state.mod_name, state.nav_name) == ('', '', '')


def test_nav_state_clear_keeps_the_language():
    """Leaving a page clears the navigation, not the chosen GUI language."""
    state = NavState(
        lang='ja-JP', config_name='oas1', mod_name='oas', nav_name='Script'
    )
    state.clear()
    assert state.lang == 'ja-JP'
    assert (state.config_name, state.mod_name, state.nav_name) == ('', '', '')


def test_conn_state_topic_name():
    assert ConnState.TOPIC_NAME == 'ConnState'


def test_conn_state_registers_exactly_the_ported_rpcs():
    """
    The restart trio of upstream is deliberately missing: it drives the
    restart manager, which has no OAS equivalent yet, and the Restart topic
    that reports its progress is not ported either (see the module docstring
    and oas/backend/README.md).
    """
    assert set(ConnState.rpc_methods) == {'set_lang', 'set_config', 'set_nav'}


async def test_set_lang_stores_an_available_language(topic):
    await topic.set_lang('ja-JP')
    assert current_state(topic).lang == 'ja-JP'


async def test_set_lang_rejects_an_unknown_language(topic):
    with pytest.raises(RpcValueError) as exc:
        await topic.set_lang('kk-KZ')
    assert 'kk-KZ' in str(exc.value)


async def test_set_lang_stores_the_request_as_given(topic):
    """
    Upstream validates the request against the available languages with the
    negotiated value, but then stores the request itself (a bare "zh" is
    accepted and kept as "zh"). Pinned here so that normalizing it later is a
    conscious decision rather than a drive-by change.
    """
    await topic.set_lang('zh')
    assert current_state(topic).lang == 'zh'


async def test_set_nav_updates_the_state(topic):
    await topic.set_nav('Script')
    assert current_state(topic).nav_name == 'Script'


async def test_set_nav_keeps_the_same_nav(topic):
    """Setting the current nav again is a no-op, not an error."""
    await topic.set_nav('Script')
    await topic.set_nav('Script')
    assert current_state(topic).nav_name == 'Script'
