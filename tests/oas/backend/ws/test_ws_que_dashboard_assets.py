"""
End-to-end: the TaskQueue, TaskRunning, TaskQueueI18n, Dashboard and
DevAssetsManager topics on /api/ws.

All five are registered in ALL_TOPIC_CLASS, so a real connection subscribes them
and reads their events: which of them sends a full event at subscribe time, the
worker push path (TaskQueue keyed patch, TaskRunning root set) and the
DevAssetsManager RPC contract.

Framework facts this test pins (both discovered while writing it):

- an EMPTY snapshot sends no full event at all (``ws_helpers.TestSource.subscribe``
  documents "None when empty", ``test_ws_conn_state`` relies on it). TaskRunning
  (data None), TaskQueueI18n (data {}) and Dashboard (no 'dashboard' nav, empty
  view) are therefore silent at subscribe time; TaskQueue ({'pending': [],
  'waiting': []}) and the DevAssetsManager folder dict are non-empty and do send
  one. Silence is asserted with a sentinel RPC: the next event on the wire must
  be the sentinel ack, never a full event of the silent topic;
- the connection carries a heartbeat (``b'ping'``, answered with ``b'pong'``),
  and the reactive layer may republish a topic full event before an RPC ack, so
  events are matched by predicate instead of by position.
"""

import msgspec
from starlette.testclient import TestClient

from oas.backend.app.app import create_app
from oas.backend.mpipe.token_backend import LOCAL_TOKEN_HEADER
from oas.backend.topic._worker import BACKEND_WORKER_MANAGER
from oas.backend.topic.dev_assets import DevAssetsManager
from oas.backend.topic.state import ConnState
from oas.backend.worker.event import ConfigEvent
from oas.config.table.key import KeyTable
from ws_helpers import TEST_TOKEN, wait_until

HEADERS = {LOCAL_TOKEN_HEADER: TEST_TOKEN}


def receive_event(ws, tries=40):
    """
    Read the next JSON event, answering the heartbeat on the way.
    """
    for _ in range(tries):
        data = ws.receive_bytes()
        if data in (b'ping', 'ping'):
            ws.send_bytes(b'pong')
            continue
        try:
            return msgspec.json.decode(data)
        except msgspec.DecodeError as e:
            print('SKIP', repr(data), e)
            continue
    raise AssertionError('no event received')


def receive_until(ws, predicate, what='event', seen=None):
    """
    Read events until one matches, printing every event read (test diagnosis).
    """
    for _ in range(40):
        event = receive_event(ws)
        print('EV', event)
        if seen is not None:
            seen.append(event)
        if predicate(event):
            return event
    raise AssertionError(f'{what} not received')


def is_full(event, topic):
    return event.get('o') == 'full' and event.get('t') == topic


def is_ack(event, rpc_id):
    return event.get('i') == rpc_id


def nav_state():
    """
    The NavState of the connected topic (same idiom as the ConnState ws tests).
    """
    items = ConnState.singleton_items()
    if len(items) != 1:
        return None
    return getattr(items[0][1], '_reactive_cache_nav_state', None)


def assets_state():
    """
    The viewport selection of the connected DevAssetsManager topic.
    """
    items = DevAssetsManager.singleton_items()
    if len(items) != 1:
        return None
    return getattr(items[0][1], '_reactive_cache_assets_state', None)


def subscribe(ws, topic):
    ws.send_json({'o': 'sub', 't': topic})
    return receive_until(ws, lambda e: is_full(e, topic), f'full of {topic}')


def set_config(ws, name='oas1'):
    ws.send_json(
        {
            'o': 'rpc',
            't': 'ConnState',
            'f': 'set_config',
            'v': {'name': name},
            'i': 'rpc-c',
        }
    )
    assert receive_until(ws, lambda e: is_ack(e, 'rpc-c'), 'set_config ack')
    assert wait_until(lambda: nav_state().config_name == name)


def assert_silent(ws, topic, sentinel):
    """
    Subscribe a topic whose data is empty: no full event may be sent, so the
    next event on the wire is the sentinel RPC ack.
    """
    seen = []
    ws.send_json({'o': 'sub', 't': topic})
    ws.send_json(
        {
            'o': 'rpc',
            't': 'ConnState',
            'f': 'set_lang',
            'v': {'lang': 'en-US'},
            'i': sentinel,
        }
    )
    receive_until(ws, lambda e: is_ack(e, sentinel), f'{topic} sentinel ack', seen)
    assert not [e for e in seen if e.get('t') == topic], seen


def test_empty_topics_and_worker_pushes(loopback_gate, config_dir):
    KeyTable('oas1').mod_set('oas')

    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        subscribe(ws, 'ConfigScan')
        set_config(ws)

        # TaskQueue data is {'pending': [], 'waiting': []}: a non-empty dict,
        # so the full event of the empty table IS sent
        event = subscribe(ws, 'TaskQueue')
        assert event['v'] == {'pending': [], 'waiting': []}

        # data None / {} / empty view: no full event at subscribe time
        assert_silent(ws, 'TaskRunning', 'rpc-s1')
        assert_silent(ws, 'TaskQueueI18n', 'rpc-s2')
        assert_silent(ws, 'Dashboard', 'rpc-s3')

        # the folder tree carries the selection, so it is sent
        event = subscribe(ws, 'DevAssetsManager')
        assert event['v']['mod_name'] == 'oas'
        assert (
            event['v']['folders'],
            event['v']['resources'],
            event['v']['assets'],
        ) == ([], {}, {})

        # worker TaskQueue push: the subscribed client gets a keyed patch
        BACKEND_WORKER_MANAGER.on_config_event(
            ConfigEvent(
                t='TaskQueue',
                c='oas1',
                v={
                    'pending': [
                        {'TaskName': 'A', 'NextRun': '2026-11-03T00:00:00+08:00'}
                    ]
                },
            )
        )
        event = receive_until(
            ws,
            lambda e: e.get('t') == 'TaskQueue' and e.get('o') == 'set',
            'TaskQueue patch',
        )
        assert event['k'] == ['pending']
        assert event['v'][0]['TaskName'] == 'A'

        # a malformed push is dropped, never stored raw
        BACKEND_WORKER_MANAGER.on_config_event(
            ConfigEvent(t='TaskQueue', c='oas1', v={'pending': 'not-a-list'})
        )

        # worker TaskRunning push: root set of the running task. It proves the
        # silent subscribe above did register the topic.
        BACKEND_WORKER_MANAGER.on_config_event(
            ConfigEvent(t='TaskRunning', c='oas1', v='A')
        )
        event = receive_until(
            ws,
            lambda e: e.get('t') == 'TaskRunning' and e.get('o') == 'set',
            'TaskRunning set',
        )
        assert event['v'] == 'A'


def test_dev_assets_rpc_contract(loopback_gate, config_dir):
    KeyTable('oas1').mod_set('oas')

    with (
        TestClient(create_app()) as client,
        client.websocket_connect('/api/ws', headers=HEADERS) as ws,
    ):
        subscribe(ws, 'ConfigScan')
        set_config(ws)
        subscribe(ws, 'DevAssetsManager')
        assert wait_until(lambda: assets_state().mod_name == 'oas')
        assert assets_state().path == 'assets'

        # every folder operation refuses (no assets manager in OAS)
        ws.send_json(
            {
                'o': 'rpc',
                't': 'DevAssetsManager',
                'f': 'resource_del',
                'v': {'names': ['~a.webp']},
                'i': 'rpc-1',
            }
        )
        event = receive_until(ws, lambda e: is_ack(e, 'rpc-1'), 'resource_del ack')
        assert 'not ported' in event['v']

        # path validation
        ws.send_json(
            {
                'o': 'rpc',
                't': 'DevAssetsManager',
                'f': 'set_path',
                'v': {'path': ''},
                'i': 'rpc-2',
            }
        )
        event = receive_until(ws, lambda e: is_ack(e, 'rpc-2'), 'set_path ack')
        assert 'Empty path' in event['v']

        ws.send_json(
            {
                'o': 'rpc',
                't': 'DevAssetsManager',
                'f': 'set_path',
                'v': {'path': '../etc'},
                'i': 'rpc-3',
            }
        )
        event = receive_until(ws, lambda e: is_ack(e, 'rpc-3'), 'set_path ack')
        assert 'Invalid path' in event['v']

        # a valid path moves the selection and republishes the folder view
        ws.send_json(
            {
                'o': 'rpc',
                't': 'DevAssetsManager',
                'f': 'set_path',
                'v': {'path': 'assets/combat'},
                'i': 'rpc-4',
            }
        )
        receive_until(ws, lambda e: is_ack(e, 'rpc-4'), 'set_path ack')
        assert wait_until(lambda: assets_state().path == 'assets/combat')

        # an unknown mod is rejected
        ws.send_json(
            {
                'o': 'rpc',
                't': 'DevAssetsManager',
                'f': 'set_mod',
                'v': {'mod_name': 'nope'},
                'i': 'rpc-5',
            }
        )
        event = receive_until(ws, lambda e: is_ack(e, 'rpc-5'), 'set_mod ack')
        assert 'No such mod' in event['v']
