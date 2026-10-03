"""
Tests for the EventSource family (alasio/backend/reactive/source.py):
subscribe snapshots, on_event apply + broadcast, fetch_init / reinit
semantics, payload freeze, singletons and idle GC of one-shot sources.
"""

import threading
import time

import pytest
import trio

from oas.backend.reactive.event import ResponseEvent
from oas.backend.reactive.source import BaseSource, ConfigSource, DiskCache, EventSource, GlobalSource, ResidentCache
from tests.oas.backend.reactive.test_source_base import MockTopic, decode


class FakeSource(EventSource):
    """
    EventSource with an event stream and a full-data source.

    - data: {'x': n, 'y': n} with n = fetch count;
    - on_event(('x', n)) replaces x (thread-writer semantics: data keys are
      replaced in place);
    - TTL = 5 for fetch freshness tests.
    """
    TOPIC_NAME = 'Fake'
    TTL = 5

    def __init__(self):
        super().__init__()
        self.data = {'x': 0, 'y': 0}
        self.fetch_count = 0

    def on_init(self):
        # runs in a worker thread when called through on_init_async
        self.fetch_count += 1
        return {'x': self.fetch_count, 'y': self.fetch_count}

    def _apply(self, event):
        key, value = event
        if self.data.get(key) == value:
            return False
        self.data[key] = value
        return True

    def _convert(self, event):
        key, value = event
        return ResponseEvent(t=self.TOPIC_NAME, o='set', k=(key,), v=value)


class NoWriterSource(EventSource):
    """
    A source without an event stream: data is only refreshed by reinit.
    Full events are encoded under the lock, no freeze contract applies.
    """
    TOPIC_NAME = 'NoWriter'
    TTL = None

    def on_init(self):
        return {'a': 1}


class TestSubscribeSnapshot:
    @pytest.mark.trio
    async def test_snapshot_contains_all_applied_events(self):
        """the full snapshot is the current data (all applied events included)"""
        source = FakeSource()
        source.data = {'x': 1, 'y': 2}
        topic = MockTopic()
        event = decode(await source.subscribe(topic))
        assert event.o == 'full'
        assert event.v == {'x': 1, 'y': 2}

    @pytest.mark.trio
    async def test_snapshot_empty_data_returns_none(self):
        """empty data returns None, no full event"""
        source = FakeSource()
        source.data = {}
        assert await source.subscribe(MockTopic()) is None


class TestOnEvent:
    @pytest.mark.trio
    async def test_no_subscriber_applies_only(self):
        """without subscribers the event is only applied, nothing scheduled"""
        source = FakeSource()
        source.on_event(('x', 5))
        assert source.data['x'] == 5

    @pytest.mark.trio
    async def test_with_subscriber_broadcasts_set(self):
        """with subscribers the event is applied and a set response broadcast"""
        source = FakeSource()
        topic = MockTopic()
        await source.subscribe(topic)
        source.on_event(('x', 5))
        await trio.testing.wait_all_tasks_blocked()
        event = decode(topic.sent[0])
        assert event.o == 'set'
        assert event.k == ('x',)
        assert event.v == 5

    @pytest.mark.trio
    async def test_no_change_no_broadcast(self):
        """an event that does not change data is not broadcast"""
        source = FakeSource()
        source.data = {'x': 1, 'y': 0}
        topic = MockTopic()
        await source.subscribe(topic)
        topic.sent.clear()
        source.on_event(('x', 1))  # same value
        await trio.testing.wait_all_tasks_blocked()
        assert topic.sent == []


class TestConvertFreeze:
    @pytest.mark.trio
    async def test_incremental_response_not_affected_by_later_apply(self):
        """
        Payload freeze: an incremental response queued by a worker thread
        references the applied event payload; a later in-place apply of
        data does not change the queued response.
        """
        source = FakeSource()
        topic = MockTopic()
        await source.subscribe(topic)
        topic.sent.clear()
        # two changes queued before the trio thread drains them
        source.on_event(('x', 1))
        source.on_event(('x', 2))
        await trio.testing.wait_all_tasks_blocked()
        events = decode(topic.sent[0])
        # both queued payloads kept their frozen values
        if isinstance(events, list):
            assert [e.v for e in events] == [1, 2]
        else:
            assert events.v == 1


class TestFetchInit:
    @pytest.mark.trio
    async def test_fetch_within_ttl_returns_none(self):
        """a second fetch inside the TTL window returns None (no re-read)"""
        source = FakeSource()
        assert await source.fetch_init() == {'x': 1, 'y': 1}
        assert source.fetch_count == 1
        # fresh: no read
        assert await source.fetch_init() is None
        assert source.fetch_count == 1

    @pytest.mark.trio
    async def test_fetch_after_ttl_rereads(self, monkeypatch):
        """after the TTL expires the data is re-read"""
        source = FakeSource()
        await source.fetch_init()
        now = [time.monotonic()]

        class Clock:
            @staticmethod
            def monotonic():
                now[0] += 10
                return now[0]

        monkeypatch.setattr(time, 'monotonic', Clock.monotonic)
        # note: EventSource freshness uses time.monotonic at check and set
        new = await source.fetch_init()
        assert new == {'x': 2, 'y': 2}
        assert source.fetch_count == 2

    @pytest.mark.trio
    async def test_fetch_force_ignores_ttl(self):
        """force=True always re-reads"""
        source = FakeSource()
        await source.fetch_init()
        assert await source.fetch_init(force=True) == {'x': 2, 'y': 2}
        assert source.fetch_count == 2

    @pytest.mark.trio
    async def test_fetch_ttl_none_always_reads(self):
        """TTL=None reads every time"""
        source = NoWriterSource()
        assert await source.fetch_init() == {'a': 1}
        assert await source.fetch_init() == {'a': 1}

    @pytest.mark.trio
    async def test_on_init_runs_in_thread(self):
        """on_init_async runs on_init in a worker thread"""
        source = FakeSource()
        main_thread = threading.get_ident()

        class ThreadAwareSource(FakeSource):
            def on_init(self):
                assert threading.get_ident() != main_thread
                return super().on_init()

        source = ThreadAwareSource()
        await source.fetch_init(force=True)
        assert source.fetch_count == 1


class TestMarkDirty:
    """
    Dirty semantics of fetch_init (mark_dirty): a dirty mark bypasses the
    TTL window, the successful read consumes the marks that existed when
    it started, marks set while the read runs survive it and a failing
    read keeps the mark.
    """

    @pytest.mark.trio
    async def test_mark_dirty_bypasses_ttl_and_is_consumed(self):
        """a dirty mark makes the next fetch re-read inside the TTL window"""
        source = FakeSource()
        assert await source.fetch_init() == {'x': 1, 'y': 1}
        source.mark_dirty()
        # fresh TTL would skip the read, dirty bypasses it
        assert await source.fetch_init() == {'x': 2, 'y': 2}
        assert source.fetch_count == 2
        # the successful read consumed the mark
        assert source._dirty == 0
        # fresh again: no read
        assert await source.fetch_init() is None
        assert source.fetch_count == 2

    @pytest.mark.trio
    async def test_marks_accumulate_consumed_together(self):
        """marks accumulate; one successful read consumes all of them"""
        source = FakeSource()
        source.mark_dirty()
        source.mark_dirty()
        assert source._dirty == 2
        await source.fetch_init()
        assert source._dirty == 0

    @pytest.mark.trio
    async def test_mark_during_read_survives(self):
        """
        a mark set while the read runs survives it (the result may
        predate the change): the read cannot tell its own mark from the
        new one, so the counter is kept and the next read happens.
        """
        source = FakeSource()
        reads = []
        marked_during_read = [False]

        async def gated_on_init():
            if not marked_during_read[0]:
                # a save lands while the read is in flight
                marked_during_read[0] = True
                source.mark_dirty()
            reads.append(1)
            return {'x': len(reads), 'y': len(reads)}

        source.on_init_async = gated_on_init
        source.mark_dirty()  # the mark that starts the read
        new = await source.fetch_init()
        assert new == {'x': 1, 'y': 1}
        # neither mark was consumed (dirty_before != dirty after)
        assert source._dirty == 2
        # dirty bypasses the TTL window: another read consumes the marks
        new = await source.fetch_init()
        assert new == {'x': 2, 'y': 2}
        assert source._dirty == 0

    @pytest.mark.trio
    async def test_failed_read_keeps_dirty(self):
        """a failing read keeps the mark: the next read retries"""
        source = FakeSource()
        calls = [0]

        async def failing_on_init():
            calls[0] += 1
            if calls[0] == 1:
                raise RuntimeError('disk boom')
            return {'x': 1, 'y': 1}

        source.on_init_async = failing_on_init
        source.mark_dirty()
        with pytest.raises(RuntimeError):
            await source.fetch_init()
        # the failed read did not consume the mark
        assert source._dirty == 1
        # the retried read succeeds and consumes it
        new = await source.fetch_init()
        assert new == {'x': 1, 'y': 1}
        assert source._dirty == 0

    @pytest.mark.trio
    async def test_ttl_none_unaffected_by_dirty(self):
        """TTL=None sources always read: a dirty mark changes nothing"""
        source = NoWriterSource()
        source.mark_dirty()
        assert await source.fetch_init() == {'a': 1}
        assert source._dirty == 0


class TestReinit:
    @pytest.mark.trio
    async def test_reinit_broadcasts_full_to_subscribers(self):
        """reinit with new data broadcasts a full event to subscribers"""
        source = FakeSource()
        topic = MockTopic()
        await source.subscribe(topic)
        topic.sent.clear()
        await source.reinit(force=True)
        await trio.testing.wait_all_tasks_blocked()
        event = decode(topic.sent[0])
        assert event.o == 'full'
        assert event.v == {'x': 1, 'y': 1}

    @pytest.mark.trio
    async def test_reinit_full_queued_behind_earlier_increments(self):
        """
        A full event is queued behind increments applied before the
        reinit (same run_sync_soon FIFO, every queueing inside the
        lock): the client never receives the full before an older event.
        """
        source = FakeSource()
        topic = MockTopic()
        await source.subscribe(topic)
        topic.sent.clear()
        # an increment is applied and its doorbell queued, then a reinit
        # runs before the trio thread drains the inbox
        source.on_event(('x', 5))
        await source.reinit(force=True)
        await trio.testing.wait_all_tasks_blocked()
        events = [decode(p) for p in topic.sent]
        assert events[0].o == 'set'
        assert events[0].k == ('x',)
        assert events[1].o == 'full'

    @pytest.mark.trio
    async def test_reinit_no_change_no_broadcast(self):
        """reinit with unchanged data does not broadcast"""
        source = NoWriterSource()
        topic = MockTopic()
        await source.subscribe(topic)
        # data must equal the read result first
        await source.reinit(force=True)
        await trio.testing.wait_all_tasks_blocked()
        topic.sent.clear()
        await source.reinit(force=True)
        await trio.testing.wait_all_tasks_blocked()
        assert topic.sent == []

    @pytest.mark.trio
    async def test_reinit_no_subscriber_refreshes_data_only(self):
        """reinit without subscribers refreshes data and broadcasts nothing"""
        source = FakeSource()
        await source.reinit(force=True)
        assert source.data == {'x': 1, 'y': 1}

    @pytest.mark.trio
    async def test_concurrent_reinit_serialized(self):
        """concurrent reinits serialize on the fetch lock: one read only"""
        source = FakeSource()

        async def double_reinit():
            async with trio.open_nursery() as nursery:
                nursery.start_soon(source.reinit)
                nursery.start_soon(source.reinit)

        await double_reinit()
        # both reinits ran (fetch_lock serializes); the second one found the
        # data fresh (TTL) and skipped the read
        assert source.fetch_count == 1


class TestGlobalConfigSingleton:
    def test_global_singleton(self):
        """GlobalSource subclasses share one global instance"""
        class GlobalFake(GlobalSource, ResidentCache):
            TOPIC_NAME = 'GlobalFake'

        try:
            a = GlobalFake()
            b = GlobalFake()
            assert a is b
        finally:
            GlobalFake.singleton_clear()

    def test_config_named_singleton(self):
        """ConfigSource instances are keyed by config name"""
        class ConfigFake(ConfigSource, ResidentCache):
            TOPIC_NAME = 'ConfigFake'

        try:
            a = ConfigFake('config_a')
            b = ConfigFake('config_a')
            c = ConfigFake('config_b')
            assert a is b
            assert a is not c
            assert a.config_name == 'config_a'
        finally:
            ConfigFake.singleton_clear()


class TestOneShotGc:
    @pytest.mark.trio
    async def test_resident_source_not_collected(self):
        """resident sources (ResidentCache) are never data-expiry collected"""
        source = FakeSource()
        topic = MockTopic()
        await source.subscribe(topic)
        source.unsubscribe(topic)
        BaseSource.gc_idle()
        assert source._subscribers == set()

    def test_disk_cache_collected_after_ttl(self, monkeypatch):
        """disk-cache global sources are removed after the data TTL expired"""

        class OneShotFake(GlobalSource, DiskCache):
            TOPIC_NAME = 'OneShotFake'
            TTL = 8

        try:
            instance = OneShotFake()
            # simulate data refreshed 20s ago (> TTL 8)
            instance._lastrun = time.monotonic() - 20
            OneShotFake.gc_idle()
            # instance must be re-registered on next use: singleton cleared
            assert OneShotFake.singleton_instance() is None
        finally:
            OneShotFake.singleton_clear()

    def test_disk_cache_fresh_instance_kept(self, monkeypatch):
        """a fresh global disk-cache instance is kept (creation base)"""

        class FreshFake(GlobalSource, DiskCache):
            TOPIC_NAME = 'FreshFake'
            TTL = 8

        try:
            instance = FreshFake()
            # never loaded: _lastrun is the creation moment (fresh)
            monkeypatch.setattr(time, 'monotonic', lambda: 100.)
            instance._lastrun = 95.
            FreshFake.gc_idle()
            assert FreshFake.singleton_instance() is instance
        finally:
            FreshFake.singleton_clear()
