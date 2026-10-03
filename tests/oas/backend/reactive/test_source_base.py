"""
Tests for the BaseSource common machinery
(alasio/backend/reactive/source.py): subscription, doorbell batching,
delivery through the subscriber contract, concurrent producers and idle GC.

Driven through minimal EventSource subclasses.
"""

import threading
import time
from typing import List
from unittest.mock import MagicMock

import msgspec
import pytest
import trio

from oas.backend.reactive.event import ResponseEvent
from oas.backend.reactive.source import _GC_CLASSES, BaseSource, DiskCache, EventSource, KeyedSource


class MockServer:
    """
    Mock ws server surface used by the mock subscriber
    """

    def __init__(self):
        self.sent = []

    def send_nowait(self, data):
        self.sent.append(data)

    async def send(self, data):
        self.sent.append(data)

    def send_lossy(self, data):
        self.sent.append(data)


class MockTopic:
    """
    Mock subscriber: deliver() records the payloads the source broadcasts
    (the BaseTopic.deliver contract). The mock always accepts: backpressure
    handling is a topic concern, tested at the ws layer.
    """

    def __init__(self, topic_name='T'):
        self.topic_name_value = topic_name
        self.conn_id = f'conn_{id(self)}'
        self.server = MockServer()

    def topic_name(self):
        return self.topic_name_value

    @property
    def sent(self):
        return self.server.sent

    def deliver(self, payload):
        """
        [Trio 线程] Source increments land here (BaseTopic.deliver contract)
        """
        self.server.sent.append(payload)


DECODER = msgspec.json.Decoder(ResponseEvent)
LIST_DECODER = msgspec.json.Decoder(List[ResponseEvent])


def decode(payload):
    """
    Decode one payload into ResponseEvent or list[ResponseEvent]

    Args:
        payload (bytes):

    Returns:
        ResponseEvent | list[ResponseEvent]:
    """
    data = msgspec.json.decode(payload)
    if isinstance(data, list):
        return LIST_DECODER.decode(payload)
    return DECODER.decode(payload)


class FakeSource(EventSource):
    """
    A minimal event source for testing the base machinery: data starts at
    {'x': 0}, on_event({'x': n}) replaces the x value, `_apply` returns
    whether the value changed.
    """
    TOPIC_NAME = 'Fake'

    def __init__(self):
        super().__init__()
        self.data = {'x': 0}

    def _apply(self, event):
        key = list(event.keys())[0] if isinstance(event, dict) else event[0]
        value = event[key] if isinstance(event, dict) else event[1]
        if self.data.get(key) == value:
            return False
        self.data[key] = value
        return True

    def _convert(self, event):
        key = event[0]
        return ResponseEvent(t=self.TOPIC_NAME, o='set', k=(key,), v=self.data[key])


class KeyedFakeSource(KeyedSource, DiskCache):
    """
    A keyed disk-cache source to verify per-class registries and the
    data-expiry GC of keyed instances (GC=True, TTL=8).
    """
    TOPIC_NAME = 'KeyedFake'
    TTL = 8

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.data = {'name': name}


@pytest.fixture(autouse=True)
def cleanup_sources():
    """Clean up keyed registries and singleton caches after each test"""
    yield
    KeyedFakeSource.singleton_clear()


class TestSubscribe:
    @pytest.mark.trio
    async def test_subscribe_returns_encoded_full(self):
        """subscribing returns encoded bytes decoding to {o:'full', v:data}"""
        source = FakeSource()
        topic = MockTopic()
        data = await source.subscribe(topic)
        assert isinstance(data, bytes)
        event = decode(data)
        assert event.t == 'Fake'
        assert event.o == 'full'
        assert event.v == {'x': 0}
        assert topic in source._subscribers

    @pytest.mark.trio
    async def test_subscribe_empty_data_returns_none(self):
        """empty data returns None (no full event)"""
        source = FakeSource()
        source.data = {}
        topic = MockTopic()
        assert await source.subscribe(topic) is None
        # still registered: later events reach the topic
        assert topic in source._subscribers

    @pytest.mark.trio
    async def test_subscribe_records_trio_token(self):
        """the trio token is recorded on the first subscribe"""
        source = FakeSource()
        assert source._trio_token is None
        await source.subscribe(MockTopic())
        assert source._trio_token is not None

    @pytest.mark.trio
    async def test_subscribe_idempotent_for_same_topic(self):
        """subscribing the same topic twice is idempotent (set semantics)"""
        source = FakeSource()
        topic = MockTopic()
        await source.subscribe(topic)
        await source.subscribe(topic)
        assert len(source._subscribers) == 1


class TestUnsubscribe:
    @pytest.mark.trio
    async def test_unsubscribe_idempotent(self):
        """unsubscribing a topic that is not subscribed does not raise"""
        source = FakeSource()
        source.unsubscribe(MockTopic())

    @pytest.mark.trio
    async def test_unsubscribed_topic_gets_no_events(self):
        """after unsubscribe new events no longer reach the topic"""
        source = FakeSource()
        topic = MockTopic()
        await source.subscribe(topic)
        source.unsubscribe(topic)
        source.on_event(('x', 1))
        await trio.testing.wait_all_tasks_blocked()
        assert topic.sent == []

    @pytest.mark.trio
    async def test_creation_time_guards_fresh_instance(self, monkeypatch):
        """a fresh source is never recycled before its TTL (creation base)"""
        monkeypatch.setattr(time, 'monotonic', lambda: 100.)
        source = FakeSource()
        # EventSource records the creation moment as _lastrun: the data-
        # expiry GC freshness base of a brand-new instance
        assert source._lastrun == 100.
        # never loaded: the first reinit must read (TTL window not applied)
        assert source._loaded is False
        await source.reinit()
        assert source._loaded is True


class TestGcIdle:
    def test_gc_membership_is_static(self):
        """only GC=True classes with a numeric TTL enter the gc list"""
        assert KeyedFakeSource in _GC_CLASSES
        assert FakeSource not in _GC_CLASSES
        # plain EventSource instances (no GC) are never collected

    @pytest.mark.trio
    async def test_no_gc_class_not_collected(self):
        """sources without GC=True are never collected"""
        source = FakeSource()
        await source.subscribe(MockTopic())
        source.unsubscribe(*list(source._subscribers))
        BaseSource.gc_idle()

    def test_keyed_source_gc_removes_expired_instance(self, monkeypatch):
        """an expired keyed disk-cache instance is removed from its registry"""
        instance = KeyedFakeSource.get('a')
        assert ('a',) in KeyedFakeSource.singleton_instances()
        monkeypatch.setattr(time, 'monotonic', lambda: 100.)
        instance._lastrun = 80.  # data 20s old > TTL 8
        KeyedFakeSource.gc_idle()
        assert KeyedFakeSource.singleton_instances() == {}

    def test_gc_removal_holds_instance_lock(self, monkeypatch):
        """
        The expiry decision and the registry removal share one critical
        section (removal runs inside the instance lock): a subscriber can
        no longer attach between them and end up stranded on a removed
        instance (see design doc 11.5).
        """
        instance = KeyedFakeSource.get('a')
        monkeypatch.setattr(time, 'monotonic', lambda: 100.)
        instance._lastrun = 80.  # data 20s old > TTL 8
        lock_held = []
        original_remove = instance._remove

        def removing():
            lock_held.append(instance._lock.locked())
            original_remove()

        instance._remove = removing
        KeyedFakeSource.gc_idle()
        assert lock_held == [True]
        assert KeyedFakeSource.singleton_instances() == {}

    def test_keyed_source_gc_keeps_fresh_instance(self, monkeypatch):
        """instances inside the TTL window are kept"""
        instance = KeyedFakeSource.get('a')
        monkeypatch.setattr(time, 'monotonic', lambda: 100.)
        instance._lastrun = 95.  # data 5s old < TTL 8
        KeyedFakeSource.gc_idle()
        assert KeyedFakeSource.singleton_instances() != {}

    def test_keyed_source_gc_never_loaded_uses_creation_base(self, monkeypatch):
        """a never-loaded instance is protected from its creation moment"""
        instance = KeyedFakeSource.get('a')
        monkeypatch.setattr(time, 'monotonic', lambda: 100.)
        # _lastrun starts at the creation moment: fresh within TTL
        instance._lastrun = 95.
        KeyedFakeSource.gc_idle()
        assert KeyedFakeSource.singleton_instances() != {}
        # older than TTL from creation -> collected
        instance._lastrun = 80.
        KeyedFakeSource.gc_idle()
        assert KeyedFakeSource.singleton_instances() == {}

    def test_disk_cache_recycles_subscribed_expired_instance(self, monkeypatch):
        """DiskCache recycles on TTL expiry regardless of subscribers"""
        instance = KeyedFakeSource.get('a')
        monkeypatch.setattr(time, 'monotonic', lambda: 100.)
        instance._lastrun = 80.
        topic = MagicMock()
        instance._subscribers.add(topic)
        KeyedFakeSource.gc_idle()
        assert KeyedFakeSource.singleton_instances() == {}

    def test_keyed_source_get_isolation(self):
        """each keyed subclass owns its own registry table"""
        class OtherKeyedSource(KeyedSource, DiskCache):
            TOPIC_NAME = 'Other'
            TTL = 8

            def __init__(self, name):
                super().__init__()
                self.name = name

        try:
            a = KeyedFakeSource.get('a')
            b = OtherKeyedSource.get('b')
            assert KeyedFakeSource.singleton_instances() is not OtherKeyedSource.singleton_instances()
            assert KeyedFakeSource.singleton_instances() == {('a',): a}
            assert OtherKeyedSource.singleton_instances() == {('b',): b}
        finally:
            OtherKeyedSource.singleton_clear()

    def test_keyed_source_get_same_key_same_instance(self):
        """get with the same key returns the same instance"""
        a1 = KeyedFakeSource.get('a')
        a2 = KeyedFakeSource.get('a')
        b = KeyedFakeSource.get('b')
        assert a1 is a2
        assert a1 is not b

    def test_keyed_source_get_none_on_keyerror(self):
        """get returns None when the constructor raises KeyError"""
        class BrokenKeyedSource(KeyedSource, DiskCache):
            TOPIC_NAME = 'Broken'
            TTL = 8

            def __init__(self, name):
                super().__init__()
                raise KeyError('gone')

        assert BrokenKeyedSource.get('a') is None
        assert BrokenKeyedSource.singleton_instances() == {}

    @pytest.mark.trio
    async def test_subscribe_reconciles_removed_instance(self):
        """
        subscribe on an instance a concurrent GC removed re-registers it
        (the registry slot is vacant and a live subscriber is arriving)
        """
        source = KeyedFakeSource.get('a')
        KeyedFakeSource.singleton_remove_if(('a',), source)  # simulated GC
        assert KeyedFakeSource.singleton_instances() == {}
        topic = MockTopic()
        await source.subscribe(topic)
        assert KeyedFakeSource.singleton_instances() == {('a',): source}

    @pytest.mark.trio
    async def test_subscribe_reconcile_keeps_newer_instance(self):
        """
        subscribe on a removed instance does NOT displace a newer instance
        that already took the slot
        """
        old = KeyedFakeSource.get('a')
        KeyedFakeSource.singleton_remove_if(('a',), old)
        new = KeyedFakeSource.get('a')
        topic = MockTopic()
        await old.subscribe(topic)  # stale flow completes on the old one
        assert KeyedFakeSource.singleton_instances() == {('a',): new}


class TestDoorbellBatching:
    @pytest.mark.trio
    async def test_doorbell_rings_once_per_batch(self):
        """inbox transitions from empty to non-empty ring exactly once"""
        source = FakeSource()
        topic = MockTopic()
        await source.subscribe(topic)
        calls = [0]
        original = source._trio_token

        class MockToken:
            def run_sync_soon(self, func):
                calls[0] += 1
                original.run_sync_soon(func)

        source._trio_token = MockToken()
        # burst of events in one thread batch: only the first rings
        for n in range(1, 6):
            source.on_event(('x', n))
        assert calls[0] == 1
        await trio.testing.wait_all_tasks_blocked()
        # a new burst after the inbox drained rings again
        source.on_event(('x', 6))
        assert calls[0] == 2

    @pytest.mark.trio
    async def test_batch_events_merged_into_array_message(self):
        """multiple queued events are delivered as one encoded array message"""
        source = FakeSource()
        topic = MockTopic()
        await source.subscribe(topic)
        for n in range(1, 4):
            source.on_event(('x', n))
        await trio.testing.wait_all_tasks_blocked()
        # exactly one delivery for the burst
        assert len(topic.sent) == 1
        events = decode(topic.sent[0])
        assert isinstance(events, list)
        assert [e.v for e in events] == [1, 2, 3]

    @pytest.mark.trio
    async def test_sync_to_trio_empty_inbox_noop(self):
        """_sync_to_trio with an empty inbox does nothing (scheduled race)"""
        source = FakeSource()
        await source.subscribe(MockTopic())
        source._sync_to_trio()


class TestDeliverContract:
    @pytest.mark.trio
    async def test_deliver_called_per_subscriber(self):
        """each subscriber receives the encoded payload through deliver()"""
        source = FakeSource()
        t1 = MockTopic()
        t2 = MockTopic()
        await source.subscribe(t1)
        await source.subscribe(t2)
        source.on_event(('x', 1))
        await trio.testing.wait_all_tasks_blocked()
        # one delivery per subscriber (no arrays: single-event batch)
        assert len(t1.sent) == 1
        assert decode(t1.sent[0]).o == 'set'
        assert decode(t1.sent[0]).v == 1
        assert len(t2.sent) == 1
        assert decode(t2.sent[0]).v == 1


class TestConcurrentProducers:
    @pytest.mark.trio
    async def test_thread_events_reach_topic_after_subscribe(self):
        """
        Events produced by a worker thread after registration are never
        lost: the final value of the subscriber equals the last event value
        (values may merge into array messages, per the FIFO contract).
        """
        source = FakeSource()
        topic = MockTopic()
        await source.subscribe(topic)

        def produce():
            for n in range(1, 101):
                source.on_event(('x', n))
                if n % 10 == 0:
                    time.sleep(0.001)

        await trio.to_thread.run_sync(produce)
        await trio.testing.wait_all_tasks_blocked()
        # decode all deliveries, flatten arrays, check value coverage
        values = []
        for payload in topic.sent:
            events = decode(payload)
            if not isinstance(events, list):
                events = [events]
            values.extend(e.v for e in events)
        assert values[-1] == 100
        # every intermediate value appeared at least once (no lost updates)
        assert len(set(values)) == 100

    @pytest.mark.trio
    async def test_unsubscribe_during_thread_events(self):
        """unsubscribing while a thread produces does not raise, no delivery after"""
        source = FakeSource()
        topic = MockTopic()
        await source.subscribe(topic)
        stop = threading.Event()

        def produce():
            n = 0
            while not stop.is_set():
                n += 1
                source.on_event(('x', n))

        thread = threading.Thread(target=produce, daemon=True)
        thread.start()
        try:
            await trio.sleep(0.01)
            source.unsubscribe(topic)
            await trio.testing.wait_all_tasks_blocked()
            count = len(topic.sent)
            await trio.sleep(0.01)
            await trio.testing.wait_all_tasks_blocked()
            # nothing delivered after the unsubscribe
            assert len(topic.sent) == count
        finally:
            stop.set()
            thread.join(timeout=2)
