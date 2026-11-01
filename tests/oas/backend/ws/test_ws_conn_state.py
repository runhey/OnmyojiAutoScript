"""
End-to-end: ConnState is the default topic of every connection.

The frontend talks to ConnState without subscribing first (the server
registers DEFAULT_TOPIC_CLASS on connect), and the GUI language of the
connection is negotiated from the ``oas_lang`` cookie, then the
Accept-Language header, then the server default. The state itself is the
reactive ``nav_state`` value that the language-dependent topics observe, so
these tests read it the way the reactive stores it.
"""

import msgspec
from starlette.testclient import TestClient

from oas.backend.app.app import create_app
from oas.backend.mpipe.token_backend import LOCAL_TOKEN_HEADER
from oas.backend.topic.state import ConnState
from oas.config.table.key import KeyTable
from ws_helpers import TEST_TOKEN, wait_until

# No password is configured, so rule A admits the connection only with a
# local token (the same header the other ws tests send).
HEADERS = {LOCAL_TOKEN_HEADER: TEST_TOKEN}


def receive_event(ws):
    """
    Read one event from the connection.

    Args:
        ws: The connected websocket

    Returns:
        dict: The decoded event
    """
    return msgspec.json.decode(ws.receive_bytes())


def nav_state():
    """
    The NavState of the connected topic, while init() is filling it in.

    The reactive keeps the computed value in an instance attribute (the
    awaitable property needs the event loop, the cache does not), so the test
    thread reads it directly.

    Returns:
        NavState | None: None while the connection has no computed state yet
    """
    items = ConnState.singleton_items()
    if len(items) != 1:
        return None
    return getattr(items[0][1], '_reactive_cache_nav_state', None)


def current_lang():
    """
    Returns:
        str | None: The negotiated language of the connection, None before init
    """
    state = nav_state()
    return None if state is None else state.lang


def test_default_topic_takes_rpcs_without_subscribing(loopback_gate):
    """
    ConnState is registered on connect, so an RPC reaches it with no "sub"
    event, and the language of the handshake is already negotiated.
    """
    with (
        TestClient(create_app()) as client,
        client.websocket_connect(
            '/api/ws', headers={**HEADERS, 'Accept-Language': 'ja-JP'}
        ) as ws,
    ):
        assert wait_until(lambda: current_lang() == 'ja-JP')

        # no sub event: the default topic is already there
        ws.send_json(
            {
                'o': 'rpc',
                't': 'ConnState',
                'f': 'set_lang',
                'v': {'lang': 'zh-CN'},
                'i': 'rpc-1',
            }
        )
        # RPC success carries no value, the ack is the rpc id only
        assert receive_event(ws) == {'t': 'ConnState', 'i': 'rpc-1'}
        assert wait_until(lambda: current_lang() == 'zh-CN')


def test_language_cookie_wins_over_the_header(loopback_gate):
    """The cookie is the user's explicit choice, so it is tried first."""
    with (
        TestClient(create_app()) as client,
        client.websocket_connect(
            '/api/ws',
            headers={
                **HEADERS,
                'Accept-Language': 'ja-JP',
                'Cookie': 'oas_lang=zh-TW',
            },
        ) as ws,
    ):
        assert wait_until(lambda: current_lang() == 'zh-TW')


def test_unknown_language_falls_back_to_the_default(loopback_gate):
    with (
        TestClient(create_app()) as client,
        client.websocket_connect(
            '/api/ws', headers={**HEADERS, 'Accept-Language': 'kk-KZ'}
        ) as ws,
    ):
        assert wait_until(lambda: current_lang() == 'en-US')


def test_set_lang_rejects_an_unknown_language(loopback_gate):
    """An RPC error travels back as an error event carrying the rpc id."""
    with (
        TestClient(create_app()) as client,
        client.websocket_connect(
            '/api/ws', headers={**HEADERS, 'Accept-Language': 'en-US'}
        ) as ws,
    ):
        ws.send_json(
            {
                'o': 'rpc',
                't': 'ConnState',
                'f': 'set_lang',
                'v': {'lang': 'kk-KZ'},
                'i': 'rpc-1',
            }
        )
        event = receive_event(ws)
        assert event['t'] == 'ConnState'
        assert event['i'] == 'rpc-1'
        assert 'kk-KZ' in event['v']
        # the rejected language never reached the state
        assert current_lang() == 'en-US'


def test_set_config_and_set_nav_drive_the_nav_state(loopback_gate, config_dir):
    """
    set_config resolves the mod from the live config scan (the GUI subscribes
    ConfigScan first), set_nav stores the navigation, and an empty config name
    clears the state on page leave.
    """
    # a config exists on disk before the frontend connects
    KeyTable('oas1').mod_set('oas')

    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        # set_config reads the config scan source, so subscribe it first
        ws.send_json({'o': 'sub', 't': 'ConfigScan'})
        assert receive_event(ws)['o'] == 'full'

        ws.send_json(
            {
                'o': 'rpc',
                't': 'ConnState',
                'f': 'set_config',
                'v': {'name': 'oas1'},
                'i': 'rpc-1',
            }
        )
        assert receive_event(ws) == {'t': 'ConnState', 'i': 'rpc-1'}
        assert wait_until(lambda: nav_state().config_name == 'oas1')
        # the mod name is calculated by the backend, not sent by the frontend
        assert nav_state().mod_name == 'oas'

        ws.send_json(
            {
                'o': 'rpc',
                't': 'ConnState',
                'f': 'set_nav',
                'v': {'name': 'Script'},
                'i': 'rpc-2',
            }
        )
        assert receive_event(ws) == {'t': 'ConnState', 'i': 'rpc-2'}
        assert wait_until(lambda: nav_state().nav_name == 'Script')

        # page leave: the empty name clears the navigation, not the language
        ws.send_json(
            {
                'o': 'rpc',
                't': 'ConnState',
                'f': 'set_config',
                'v': {'name': ''},
                'i': 'rpc-3',
            }
        )
        assert receive_event(ws) == {'t': 'ConnState', 'i': 'rpc-3'}
        assert wait_until(lambda: nav_state().config_name == '')
        assert nav_state().nav_name == ''
        assert nav_state().lang == 'en-US'


def test_set_config_rejects_a_missing_config(loopback_gate, config_dir):
    # one config on disk, so the scan has data and the connection gets a full
    # event to read (an empty snapshot sends nothing at all)
    KeyTable('oas1').mod_set('oas')

    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        ws.send_json({'o': 'sub', 't': 'ConfigScan'})
        event = receive_event(ws)
        assert event['o'] == 'full'
        assert 'oas1' in event['v']

        ws.send_json(
            {
                'o': 'rpc',
                't': 'ConnState',
                'f': 'set_config',
                'v': {'name': 'oas9'},
                'i': 'rpc-1',
            }
        )
        event = receive_event(ws)
        assert event['i'] == 'rpc-1'
        assert 'No such config' in event['v']
        assert nav_state().config_name == ''


def test_set_config_rejects_a_protected_name(loopback_gate, config_dir):
    """The name is validated before the scan is asked for it."""
    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        ws.send_json(
            {
                'o': 'rpc',
                't': 'ConnState',
                'f': 'set_config',
                'v': {'name': 'gui'},
                'i': 'rpc-1',
            }
        )
        event = receive_event(ws)
        assert event['i'] == 'rpc-1'
        assert 'protected' in event['v']
        assert nav_state().config_name == ''
