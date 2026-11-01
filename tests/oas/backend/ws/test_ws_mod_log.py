"""
End-to-end: the ModList, ModHistory, Restart and Log topics on /api/ws.

All four are registered in ALL_TOPIC_CLASS, so a real connection subscribes
them and reaches the real source behind each one. The Log test drives the log
stream the way the worker pipe reader will -- a plain thread calling
LogCache.on_event -- and reads the batched push back off the wire, which also
proves the doorbell (AnyIO.call_soon) and the lossy send path end to end.
"""

import msgspec
from starlette.testclient import TestClient

from oas.backend.app.app import create_app
from oas.backend.mpipe.token_backend import LOCAL_TOKEN_HEADER
from oas.backend.topic.log import LogCache
from oas.backend.topic.restart import RestartSource
from oas.backend.worker.event import ConfigEvent
from oas.config.table.key import KeyTable
from ws_helpers import TEST_TOKEN

# No password is configured, so rule A admits the connection only with a
# local token (the same header the other ws tests send).
HEADERS = {LOCAL_TOKEN_HEADER: TEST_TOKEN}

MOD_NAME = 'oas'
CONFIG_NAME = 'oas1'
LOG_LINES = 2


def receive_event(ws):
    """
    Read one event from the connection.

    Args:
        ws: The connected websocket

    Returns:
        dict: The decoded event
    """
    return msgspec.json.decode(ws.receive_bytes())


def test_mod_list_pushes_the_declared_mods(loopback_gate):
    """
    The mod list is the declared entry table of the OAS mod layer, read once
    and cached.
    """
    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        ws.send_json({'o': 'sub', 't': 'ModList'})
        event = receive_event(ws)
        assert event['t'] == 'ModList'
        assert event['o'] == 'full'
        assert [option['value'] for option in event['v']] == [MOD_NAME]
        assert [option['label'] for option in event['v']] == [MOD_NAME]


def test_mod_history_pushes_one_entry_per_mod(loopback_gate):
    """
    Every mod gets an entry: data plus, when the packed history is missing or
    broken, the error that explains it.
    """
    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        ws.send_json({'o': 'sub', 't': 'ModHistory'})
        event = receive_event(ws)
        assert event['t'] == 'ModHistory'
        assert event['o'] == 'full'
        assert set(event['v']) == {MOD_NAME}
        assert isinstance(event['v'][MOD_NAME]['data'], list)


def test_restart_reports_the_flow_its_manager_publishes(loopback_gate):
    """
    The topic is passive: nothing publishes a flow yet (the restart manager is
    not ported), so the test plays it and applies a phase to the resident
    source; a subscriber then receives it as a full.
    """
    assert RestartSource()._apply('stopping') is True

    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        ws.send_json({'o': 'sub', 't': 'Restart'})
        event = receive_event(ws)
        assert event['t'] == 'Restart'
        assert event['o'] == 'full'
        assert event['v']['phase'] == 'stopping'


def test_log_streams_the_worker_pipe_into_the_subscription(loopback_gate, config_dir):
    """
    The pipe reader is a thread outside the event loop; the test thread plays
    it, and every line it pushes must arrive exactly once and in order.
    """
    # the GUI binds a config before it subscribes the log stream
    KeyTable(CONFIG_NAME).mod_set(MOD_NAME)

    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        ws.send_json({'o': 'sub', 't': 'ConfigScan'})
        assert receive_event(ws)['o'] == 'full'

        ws.send_json(
            {
                'o': 'rpc',
                't': 'ConnState',
                'f': 'set_config',
                'v': {'name': CONFIG_NAME},
                'i': 'rpc-1',
            }
        )
        assert receive_event(ws) == {'t': 'ConnState', 'i': 'rpc-1'}

        ws.send_json({'o': 'sub', 't': 'Log'})
        # an empty log still answers with a full: switching the config must
        # clear the log view the frontend already shows
        assert receive_event(ws) == {'t': 'Log', 'o': 'full', 'v': []}

        # the pipe reader thread: the doorbell batches whatever it finds
        cache = LogCache(CONFIG_NAME)
        cache.on_event(ConfigEvent(t='Log', v={'t': 1.0, 'l': 'INFO', 'm': 'one'}))
        cache.on_event(ConfigEvent(t='Log', v={'t': 2.0, 'l': 'ERROR', 'm': 'two'}))

        # read until both lines arrived, however the doorbell batched them
        lines = []
        while len(lines) < LOG_LINES:
            event = msgspec.json.decode(ws.receive_bytes())
            lines.extend(event if isinstance(event, list) else [event])
        assert [line['v']['m'] for line in lines] == ['one', 'two']
