"""
The ws layer: handshake, subscribe, delivery, unsubscribe, rpc, heartbeat and
shutdown.
"""

import asyncio

import msgspec
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from oas.backend.anyio import AnyIO
from oas.backend.mpipe.token_backend import ELECTRON_TOKEN_HEADER
from oas.backend.ws.ws_server import WebsocketTopicServer
from ws_helpers import (
    TEST_TOKEN,
    TEST_TOPIC,
    FastPingServer,
    TestServer,
    TestTopic,
    create_test_app,
    encode_add,
    encode_full,
    wait_until,
)


def connect(client, token=TEST_TOKEN):
    """
    Handshake a websocket with the electron token, or without any token.

    Args:
        client (TestClient): The client whose app serves /ws
        token (str): Token to send, '' to send none

    Returns:
        The connected websocket context manager
    """
    headers = {ELECTRON_TOKEN_HEADER: token} if token else {}
    return client.websocket_connect('/ws', headers=headers)


def receive_event(ws):
    """
    Read one event from the connection.

    Args:
        ws: The connected websocket

    Returns:
        dict: The decoded event
    """
    return msgspec.json.decode(ws.receive_bytes())


def subscribe(ws, topic=TEST_TOPIC):
    """
    Send a subscribe event.

    Args:
        ws: The connected websocket
        topic (str): Topic name to subscribe
    """
    ws.send_json({'o': 'sub', 't': topic})


def push_from_loop(source, payload):
    """
    Deliver one increment the way a source does: on the loop thread, through
    the bridge doorbell (AnyIO.call_soon), never from the test thread.

    Args:
        source (TestSource): Source broadcasting the increment
        payload (bytes): The encoded increment
    """
    assert AnyIO.call_soon(source.push, payload) is True


def test_connection_without_a_token_is_refused():
    """
    The login layer closes an unauthenticated connection after accept, with
    the code the frontend reads as "session over".
    """
    with TestClient(create_test_app()) as client, connect(client, token='') as ws:
        with pytest.raises(WebSocketDisconnect) as refused:
            ws.receive_bytes()
        assert refused.value.code == 4001


def test_connection_is_registered_while_it_lives(source):
    """
    An authenticated connection appears in the class registry and leaves it
    when it goes away (registry: the connection manager of the server).
    """
    with TestClient(create_test_app()) as client:
        with connect(client) as ws:
            subscribe(ws)
            assert wait_until(lambda: source.subscribers)
            assert wait_until(lambda: len(WebsocketTopicServer.active) == 1)
        assert wait_until(lambda: not WebsocketTopicServer.active)


def test_sub_sends_the_full_snapshot(source):
    """
    A subscribe binds the topic to its source and the snapshot goes out as
    the full event of that topic.
    """
    source.snapshot = encode_full({'n': 1})
    with TestClient(create_test_app()) as client, connect(client) as ws:
        subscribe(ws)
        assert receive_event(ws) == {'t': TEST_TOPIC, 'o': 'full', 'v': {'n': 1}}
        assert len(source.subscribers) == 1


def test_sub_on_an_unknown_topic_answers_with_an_error():
    """
    A refused subscribe answers with an error event instead of closing the
    connection.
    """
    with TestClient(create_test_app()) as client, connect(client) as ws:
        subscribe(ws, topic='nope')
        assert receive_event(ws) == {
            't': 'error',
            'o': 'full',
            'v': 'AccessDenied: No such topic: "nope"',
        }


def test_increment_is_delivered_in_order(source):
    """
    Increments broadcast by the source reach the subscribed client, in the
    order the source pushed them.
    """
    source.snapshot = encode_full({'n': 0})
    with TestClient(create_test_app()) as client, connect(client) as ws:
        subscribe(ws)
        assert receive_event(ws)['o'] == 'full'
        push_from_loop(source, encode_add({'n': 1}))
        push_from_loop(source, encode_add({'n': 2}))
        assert [receive_event(ws)['v'] for _ in range(2)] == [{'n': 1}, {'n': 2}]


def test_unsub_releases_the_subscription_and_the_topic(source):
    """
    Unsubscribe unregisters the topic from its source and drops the topic
    instance, so a later push has nowhere to go.
    """
    source.snapshot = encode_full({'n': 0})
    with TestClient(create_test_app()) as client, connect(client) as ws:
        subscribe(ws)
        assert receive_event(ws)['o'] == 'full'
        ws.send_json({'o': 'unsub', 't': TEST_TOPIC})
        assert wait_until(lambda: not source.subscribers)
        assert wait_until(lambda: TestTopic.singleton_instances() == {})


def test_rpc_before_subscribe_answers_with_an_error():
    """
    An rpc for a topic that is not subscribed answers with an error carrying
    the rpc id, and the connection stays alive.
    """
    with TestClient(create_test_app()) as client, connect(client) as ws:
        ws.send_json({'o': 'rpc', 't': TEST_TOPIC, 'f': 'echo', 'i': 'r1', 'v': 'x'})
        assert receive_event(ws) == {
            't': TEST_TOPIC,
            'v': 'Cannot do RPC before subscribing topic: "test"',
            'i': 'r1',
        }


def test_rpc_success_answers_with_the_rpc_id(source):
    """
    A successful rpc answers with the rpc id and no value, and the call
    really reached the topic.
    """
    source.snapshot = encode_full({'n': 0})
    with TestClient(create_test_app()) as client, connect(client) as ws:
        subscribe(ws)
        assert receive_event(ws)['o'] == 'full'
        ws.send_json(
            {
                'o': 'rpc',
                't': TEST_TOPIC,
                'f': 'echo',
                'i': 'r1',
                'v': {'value': 'hello'},
            }
        )
        assert receive_event(ws) == {'t': TEST_TOPIC, 'i': 'r1'}
        topic = next(iter(TestTopic.singleton_instances().values()))
        assert wait_until(lambda: getattr(topic, 'last_rpc', None) == 'hello')


def test_heartbeat_pings_and_a_pong_keeps_the_connection():
    """
    An idle connection is pinged, and a pong keeps it alive: the next ping
    proves the connection survived the first one.
    """
    with TestClient(create_test_app(FastPingServer)) as client, connect(client) as ws:
        assert ws.receive_bytes() == b'ping'
        ws.send_bytes(b'pong')
        assert ws.receive_bytes() == b'ping'


def test_heartbeat_closes_the_connection_without_a_pong():
    """
    No pong within PONG_TIMEOUT closes the connection.
    """
    with TestClient(create_test_app(FastPingServer)) as client, connect(client) as ws:
        assert ws.receive_bytes() == b'ping'
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_bytes()
        assert closed.value.code == 1000
        assert closed.value.reason == 'Pong timeout'


def test_close_all_connections_closes_with_1001(source):
    """
    The server shutdown request reaches every connection: it closes with
    1001 instead of being dropped.
    """
    with TestClient(create_test_app()) as client, connect(client) as ws:
        subscribe(ws)
        assert wait_until(lambda: source.subscribers)
        future = asyncio.run_coroutine_threadsafe(
            WebsocketTopicServer.close_all_connections(), AnyIO.loop()
        )
        future.result(timeout=5)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_bytes()
        assert closed.value.code == 1001
        assert closed.value.reason == 'Server shutdown'


def test_lifespan_asks_the_connections_to_close_on_shutdown(monkeypatch):
    """
    Stopping the app (the server shutdown path) asks the active connections
    to close before the global task group goes down.
    """
    calls = []

    async def recorder():
        calls.append(True)

    monkeypatch.setattr(WebsocketTopicServer, 'close_all_connections', recorder)
    with TestClient(create_test_app()):
        pass
    assert calls == [True]


def test_lifespan_rearms_the_termination_event():
    """
    Every app run watches a fresh termination event: the class attribute
    outlives one run, and a left-set one would close every later connection
    immediately.
    """
    with TestClient(create_test_app()):
        first = WebsocketTopicServer.server_terminated
    with TestClient(create_test_app()):
        assert WebsocketTopicServer.server_terminated is not first


def test_backlogged_connection_drains_the_outbox_in_order(source):
    """
    A connection that does not keep up gets its increments through the
    bounded outbox of the topic, and still receives all of them in order.
    """
    source.snapshot = encode_full({'n': 0})
    total = TestServer.SEND_BUFFER_LENGTH + 16
    with TestClient(create_test_app()) as client, connect(client) as ws:
        subscribe(ws)
        assert receive_event(ws)['o'] == 'full'

        async def push_many():
            for i in range(total):
                source.push(encode_add({'n': i}))

        # the fast path fills the send buffer, the rest waits in the outbox:
        # start_soon needs an async task context, which a bare loop callback
        # does not have, so the pushes go over as a coroutine
        future = asyncio.run_coroutine_threadsafe(push_many(), AnyIO.loop())
        future.result(timeout=5)
        received = [receive_event(ws)['v']['n'] for _ in range(total)]
        assert received == list(range(total))
