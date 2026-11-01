"""
End-to-end: the app serves /api/ws, and the ConfigScan topic is bound to
its real disk-cache source.

The other ws tests pin the layer with a duck-typed source; this one walks
the whole chain the frontend walks: handshake, subscribe, the full event
of a real source, an RPC that refreshes that source (a second full event),
unsubscribe and disconnect cleanup.
"""

import msgspec
import pytest
from starlette.testclient import TestClient

from oas.backend.app.app import create_app
from oas.backend.mpipe.token_backend import LOCAL_TOKEN_HEADER
from oas.backend.topic.scan import ConfigScan, ConfigScanSource
from oas.config.table.config import ConfigTable
from oas.config.table.key import KeyTable
from oas.config.table.scan import ScanTable
from oas.db.conn import SQLITE_POOL
from oas.ext import env
from oas.ext.path import PathStr
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


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """
    Isolate the repository config directory, as tests/oas/config does: the
    scan reads and writes ``config/*.db`` under ``env.PROJECT_ROOT``.

    Yields:
        PathStr: The temporary project root
    """
    root = PathStr.new(str(tmp_path))
    monkeypatch.setattr(env, 'PROJECT_ROOT', root)
    (tmp_path / 'config').mkdir(parents=True, exist_ok=True)

    ConfigScan.singleton_clear()
    ConfigScanSource.singleton_clear()
    ScanTable.singleton_clear()
    # the table must exist before the source scans (see tests/oas/config)
    ScanTable().create_table()

    yield root

    ConfigScan.singleton_clear()
    ConfigScanSource.singleton_clear()
    ScanTable.singleton_clear()
    for name in ('gui', 'oas1', 'oas2'):
        ConfigTable.singleton_remove(name)
        KeyTable.singleton_remove(name)
        SQLITE_POOL.delete_file(str(root / 'config' / f'{name}.db'))


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
