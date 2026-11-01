"""
End-to-end: the Worker topic on /api/ws.

The topic is registered in ALL_TOPIC_CLASS, so a real connection subscribes it
and reaches the resident source behind it. The states are reported from
outside the event loop (the worker recv thread does it in production), which
is what the source's docstring promises: the tests play that thread here.
"""

import msgspec
from starlette.testclient import TestClient

from oas.backend.app.app import create_app
from oas.backend.mpipe.token_backend import LOCAL_TOKEN_HEADER
from oas.backend.topic._worker import WorkerSource
from ws_helpers import TEST_TOKEN

# No password is configured, so rule A admits the connection only with a
# local token (the same header the other ws tests send).
HEADERS = {LOCAL_TOKEN_HEADER: TEST_TOKEN}

CONFIG_NAME = 'oas1'


def receive_event(ws):
    """
    Read one event from the connection.

    Args:
        ws: The connected websocket

    Returns:
        dict: The decoded event
    """
    return msgspec.json.decode(ws.receive_bytes())


def test_worker_reports_the_states_of_a_running_backend(loopback_gate):
    """
    A worker that started before the page opened is still in the source: the
    snapshot is the resident state dict.
    """
    assert WorkerSource()._apply((CONFIG_NAME, 'running')) is True

    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        ws.send_json({'o': 'sub', 't': 'Worker'})
        event = receive_event(ws)
        assert event['t'] == 'Worker'
        assert event['o'] == 'full'
        assert event['v'] == {CONFIG_NAME: 'running'}


def test_worker_pushes_state_changes_and_idle_deletes_the_entry(loopback_gate):
    """
    Subscribing hands the resident state over and every later change is
    pushed; "idle" deletes the key instead of setting it.

    An empty source answers with nothing at all (BaseSource.subscribe returns
    None for empty data, as an empty config directory does on ConfigScan), so
    the connection starts from a state.
    """
    assert WorkerSource()._apply((CONFIG_NAME, 'running')) is True

    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        ws.send_json({'o': 'sub', 't': 'Worker'})
        event = receive_event(ws)
        assert (event['t'], event['o'], event['v']) == (
            'Worker',
            'full',
            {CONFIG_NAME: 'running'},
        )

        # the worker recv thread: no loop, no matter for the source
        WorkerSource().on_event((CONFIG_NAME, 'scheduler-waiting'))
        event = receive_event(ws)
        assert (event['t'], event['o'], event['k'], event['v']) == (
            'Worker',
            'set',
            [CONFIG_NAME],
            'scheduler-waiting',
        )

        WorkerSource().on_event((CONFIG_NAME, 'idle'))
        event = receive_event(ws)
        assert (event['t'], event['o'], event['k']) == (
            'Worker',
            'del',
            [CONFIG_NAME],
        )


def test_worker_start_rejects_an_unknown_config(loopback_gate):
    """
    The RPC reaches get_mod, which reports the missing config back over the
    wire with the rpc id.
    """
    # a state first: an empty source sends no full at all
    assert WorkerSource()._apply((CONFIG_NAME, 'running')) is True

    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        ws.send_json({'o': 'sub', 't': 'Worker'})
        receive_event(ws)

        ws.send_json(
            {
                'o': 'rpc',
                't': 'Worker',
                'f': 'start',
                'v': {'config': 'nope'},
                'i': 'rpc-1',
            }
        )
        event = receive_event(ws)
        assert event['t'] == 'Worker'
        assert event['i'] == 'rpc-1'
        assert 'nope' in event['v']
