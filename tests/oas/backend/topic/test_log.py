"""
Unit tests of the Log topic and its LogCache.

The cache is the interesting half: it is the lock-free bridge from the worker
pipe thread to the event loop, so the tests drive it exactly the way the pipe
reader does (a plain thread calling on_event) and check the three guarantees
of its docstring -- no loss, no duplicate, no reorder.

The topic half is covered over the real /api/ws endpoint by
tests/oas/backend/ws/test_ws_mod_log.py.
"""

import json

import anyio
import msgspec
import pytest

from oas.backend.topic.log import Log, LogCache
from oas.backend.topic.state import ConnState
from oas.backend.worker.event import DECODER_CACHE, ConfigEvent

pytestmark = pytest.mark.anyio

CONN_ID = 'test-conn'
CONFIG_NAME = 'oas1'


class FakeTopic:
    """
    Minimal stand-in for a Log subscriber.

    The push path only needs TOPIC_NAME and a server with send_lossy, the
    same duck typing the source tests use.
    """

    TOPIC_NAME = 'Log'

    def __init__(self):
        self.batches: 'list[bytes]' = []
        self.server = self

    def send_lossy(self, data):
        self.batches.append(data)

    def decoded(self) -> list:
        """Every pushed batch, decoded back to plain events."""
        out = []
        for batch in self.batches:
            out.extend(json.loads(batch))
        return out


@pytest.fixture(autouse=True)
def clear_state():
    """LogCache is keyed by config name and ConnState by connection id."""
    LogCache.singleton_clear()
    yield
    LogCache.singleton_clear()
    ConnState.singleton_remove(CONN_ID)
    Log.singleton_remove(CONN_ID)


def log_event(message: str) -> ConfigEvent:
    """A worker log event, the shape the pipe reader decodes."""
    return ConfigEvent(t='Log', v={'t': 1.0, 'l': 'INFO', 'm': message})


async def drain_push():
    """
    Let the doorbell callback run.

    AnyIO.call_soon schedules on the loop, so the push happens one loop
    iteration after on_event; nothing else in these tests awaits in between.
    """
    await anyio.sleep(0.05)


async def test_subscribe_of_an_empty_cache_sends_an_empty_full():
    """
    Unlike ConfigScan, an empty Log still answers with a full: switching the
    config must clear the log view the frontend already shows.
    """
    cache = LogCache(CONFIG_NAME)
    topic = FakeTopic()
    event = json.loads(await cache.subscribe(topic))
    assert event == {'t': 'Log', 'o': 'full', 'v': []}


async def test_on_event_without_subscribers_only_fills_the_cache():
    """No subscriber: the pipe thread must not touch the loop at all."""
    cache = LogCache(CONFIG_NAME)
    cache.on_event(log_event('first'))
    assert [e.v['m'] for e in cache._cache] == ['first']
    assert list(cache._inbox) == []


async def test_the_doorbell_batches_every_event_into_one_push():
    cache = LogCache(CONFIG_NAME)
    topic = FakeTopic()
    await cache.subscribe(topic)
    cache.on_event(log_event('first'))
    cache.on_event(log_event('second'))
    # the second event found a non-empty inbox: no second doorbell
    await drain_push()
    assert len(topic.batches) == 1
    assert [e['v']['m'] for e in topic.decoded()] == ['first', 'second']
    assert list(cache._inbox) == []


async def test_subscribe_deduplicates_what_is_already_in_flight():
    """
    The overlap rule: whatever is in the inbox is also already in the cache
    (the producer writes the inbox first), so the snapshot must drop the
    overlapping tail. Both are read before the doorbell callback runs.
    """
    cache = LogCache(CONFIG_NAME)
    first = FakeTopic()
    await cache.subscribe(first)
    cache.on_event(log_event('one'))
    cache.on_event(log_event('two'))

    second = FakeTopic()
    snapshot = json.loads(await cache.subscribe(second))
    assert [e.v['m'] for e in cache._cache] == ['one', 'two']
    assert snapshot['o'] == 'full'
    assert snapshot['v'] == []


async def test_a_late_subscriber_gets_the_whole_cache():
    """Once the inbox is drained, the full is the cache history."""
    cache = LogCache(CONFIG_NAME)
    topic = FakeTopic()
    await cache.subscribe(topic)
    cache.on_event(log_event('one'))
    await drain_push()

    late = FakeTopic()
    snapshot = json.loads(await cache.subscribe(late))
    # the full carries the log values themselves, one per cached event
    assert [event['m'] for event in snapshot['v']] == ['one']


async def test_unsubscribe_stops_the_push_and_clears_the_inbox():
    cache = LogCache(CONFIG_NAME)
    topic = FakeTopic()
    await cache.subscribe(topic)
    cache.unsubscribe(topic)
    cache.on_event(log_event('after'))
    await drain_push()
    assert topic.batches == []
    assert list(cache._inbox) == []


async def test_the_cache_keeps_only_the_last_500_events():
    cache = LogCache(CONFIG_NAME)
    for i in range(520):
        cache.on_event(log_event(f'line-{i}'))
    assert len(cache._cache) == 500
    assert cache._cache[0].v['m'] == 'line-20'


async def test_log_topic_without_a_config_has_no_source():
    topic = Log(CONN_ID, None)
    assert await topic.get_source() is None


async def test_log_topic_resolves_the_cache_of_the_bound_config():
    state_topic = ConnState(CONN_ID, None)
    topic = Log(CONN_ID, None)
    state = await state_topic.nav_state
    state.config_name = CONFIG_NAME
    await state_topic.nav_state.mutate()
    source = await topic.get_source()
    assert source is LogCache(CONFIG_NAME)
    assert source.config_name == CONFIG_NAME


def test_worker_events_decode_with_the_shared_decoder():
    """The pipe reader decodes the worker protocol with DECODER_CACHE."""
    event = DECODER_CACHE.CONFIG_EVENT.decode(
        msgspec.msgpack.encode(
            ConfigEvent(t='Log', v={'t': 1.0, 'l': 'INFO', 'm': 'hi'})
        )
    )
    assert event.t == 'Log'
    assert event.v['m'] == 'hi'
