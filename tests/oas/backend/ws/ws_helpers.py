"""
Test doubles of the ws layer: a duck-typed source, one topic, one server.

The real reactive integration is covered by its own tests:
test_ws_config_scan.py binds ConfigScan to its real disk-cache source and
test_ws_conn_state.py covers the ConnState default topic. These tests pin the
ws layer itself with a duck-typed source: handshake, subscribe, delivery,
unsubscribe, rpc, heartbeat and shutdown.
"""

import time

from starlette.websockets import WebSocket

from oas.backend.app.app import create_app
from oas.backend.reactive.base_rpc import rpc
from oas.backend.reactive.event import ResponseEvent
from oas.backend.ws.ws_server import RESPONSE_EVENT_ENCODER, WebsocketTopicServer
from oas.backend.ws.ws_topic import BaseTopic

TEST_TOKEN = 'test-local-token'
TEST_TOPIC = 'test'


def encode_full(value):
    """
    The full event of a subscribe: what a source snapshot encodes to.

    Args:
        value: The topic data to send

    Returns:
        bytes: The encoded ResponseEvent
    """
    return RESPONSE_EVENT_ENCODER.encode(ResponseEvent(t=TEST_TOPIC, o='full', v=value))


def encode_add(value):
    """
    An increment event: what a source broadcasts on a change.

    Args:
        value: The increment payload

    Returns:
        bytes: The encoded ResponseEvent
    """
    return RESPONSE_EVENT_ENCODER.encode(ResponseEvent(t=TEST_TOPIC, v=value))


def wait_until(predicate, timeout=5.0):
    """
    Poll a predicate from the test thread (the server runs on its own loop).

    Args:
        predicate (callable): Condition to poll
        timeout (float): Seconds to keep polling

    Returns:
        bool: Whether the predicate held before the timeout
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


class TestSource:
    """
    Minimal source: only what a topic calls -- subscribe() returning the
    encoded snapshot, and unsubscribe(). push() is the test-side increment.
    """

    # a helper imported by the test modules, not a test case of its own
    __test__ = False

    def __init__(self, snapshot=None):
        self.snapshot = snapshot
        self.subscribers = []

    async def subscribe(self, sub):
        """
        Register a subscriber and hand over the current data.

        Args:
            sub: The subscribing topic

        Returns:
            bytes | None: The encoded full event, None when empty
        """
        self.subscribers.append(sub)
        return self.snapshot

    def unsubscribe(self, sub):
        """
        Drop a subscriber.

        Args:
            sub: The unsubscribing topic
        """
        try:
            self.subscribers.remove(sub)
        except ValueError:
            pass

    def push(self, payload):
        """
        Broadcast one increment to every subscriber (the source side of the
        loop doorbell: a topic's deliver() is called from here).

        Args:
            payload (bytes): The encoded increment
        """
        for sub in list(self.subscribers):
            sub.deliver(payload)


class TestTopic(BaseTopic):
    TOPIC_NAME = TEST_TOPIC
    # a helper imported by the test modules, not a test case of its own
    __test__ = False
    # the source handed to every connection of a test (set by the fixture)
    source = None

    async def get_source(self):
        """
        Returns:
            TestSource | None: The source of this test
        """
        return self.source

    @rpc
    async def echo(self, value):
        # RPC success sends no value: the ack event carries the rpc id only,
        # the data itself flows through the subscription
        self.last_rpc = value


class TestServer(WebsocketTopicServer):
    """A server that serves exactly one topic."""

    # a helper imported by the test modules, not a test case of its own
    __test__ = False

    ALL_TOPIC_CLASS = {TEST_TOPIC: TestTopic}


class FastPingServer(TestServer):
    """Heartbeat timings short enough for a test to wait on."""

    PING_INTERVAL = 0.05
    PONG_TIMEOUT = 0.2


def create_test_app(server_cls=TestServer):
    """
    The real app skeleton (loop bridge, global task group, lifespan) plus a
    /ws endpoint. The real /api/ws route lands with the business topics.

    Args:
        server_cls (type): The server class serving the endpoint

    Returns:
        FastAPI: The application
    """
    app = create_app()

    @app.websocket('/ws')
    async def ws_endpoint(ws: WebSocket):
        await server_cls.endpoint(ws)

    return app
