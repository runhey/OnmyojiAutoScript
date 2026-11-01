"""
End-to-end: the app serves /api/ws, and the ConfigScan topic is bound to
its real disk-cache source.

The other ws tests pin the layer with a duck-typed source; this one walks
the whole chain the frontend walks: handshake, subscribe, the full event
of a real source, an RPC that refreshes that source (a second full event),
unsubscribe and disconnect cleanup.
"""

import msgspec
from starlette.testclient import TestClient

from oas.backend.app.app import create_app
from oas.backend.mpipe.token_backend import LOCAL_TOKEN_HEADER
from oas.backend.topic.scan import ConfigScanSource
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


def test_config_scan_carries_a_local_config_over_the_real_route(
    deploy_config, loopback_gate, config_dir
):
    """
    Subscribe ConfigScan on the real /api/ws route: the full event carries
    the config on disk, the config_add RPC refreshes the source and pushes
    the new data, and unsubscribing drops the source subscription.
    """
    # a config exists on disk before the frontend connects
    KeyTable('oas1').mod_set('oas')

    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        # subscribe: the full event is the encoded snapshot of the source
        ws.send_json({'o': 'sub', 't': 'ConfigScan'})
        event = receive_event(ws)
        assert event['t'] == 'ConfigScan'
        assert event['o'] == 'full'
        assert event['v']['oas1']['mod'] == 'oas'

        # an RPC mutates the data, the source rescans and pushes again
        ws.send_json(
            {
                'o': 'rpc',
                't': 'ConfigScan',
                'f': 'config_rename',
                'v': {'old_name': 'oas1', 'new_name': 'oas2'},
                'i': 'rpc-1',
            }
        )
        event = receive_event(ws)
        assert event['t'] == 'ConfigScan'
        assert event['o'] == 'full'
        assert 'oas2' in event['v']

        # unsubscribe: the source keeps no subscriber of this connection
        ws.send_json({'o': 'unsub', 't': 'ConfigScan'})
        source = ConfigScanSource()
        assert wait_until(lambda: not source._subscribers)


def test_disconnect_releases_the_source(deploy_config, loopback_gate, config_dir):
    """
    Dropping the connection unsubscribes its topics from the source: the
    ws server sweeps every subscribed topic in cleanup().
    """
    KeyTable('oas1').mod_set('oas')

    with TestClient(create_app()) as client:
        with client.websocket_connect('/api/ws', headers=HEADERS) as ws:
            ws.send_json({'o': 'sub', 't': 'ConfigScan'})
            event = receive_event(ws)
            assert event['o'] == 'full'
            assert wait_until(lambda: bool(ConfigScanSource()._subscribers))

        source = ConfigScanSource()
        assert wait_until(lambda: not source._subscribers)
