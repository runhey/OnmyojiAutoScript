"""
Tests for the resource caches in alasio/ext/cache/resource.py.

Both caches answer get() with the same object for the same file, loading it at
most once even when the callers are concurrent (double-checked locking on a
per-file pre-resource lock). ResourceCacheTTL additionally records the last use
of every entry and releases the entries that were idle for more than `idle`
seconds in gc(), while ResourceCache releases everything on gc().

The caches are driven through subclasses whose load_resource counts its calls,
so that "loaded once" becomes directly observable. The clock is frozen with
PatchTime: the idle window is measured on a monotonic clock, and a test that
waits for the window to pass would be a test that sleeps for a minute.
"""

import threading
import time

import pytest

from oas.ext.cache.resource import ResourceCache, ResourceCacheTTL
from oas.testing.patch_time import PatchTime


@pytest.fixture
def clock():
    """
    A monotonic clock that only moves when the test moves it

    time.monotonic() returns the timestamp of the PatchTime and shift()
    advances it.
    """
    with PatchTime(1000.) as patch:
        yield patch


class HookedDict(dict):
    """
    A dict that runs a hook right after a key was set.

    Installing it as the cache storage puts the hook exactly between the two
    writes that publish an entry, which makes that interleaving deterministic
    (a gc() there sees the entry before its last use is recorded).
    """

    def __init__(self):
        super().__init__()
        self.hook = None

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        hook, self.hook = self.hook, None
        if hook is not None:
            hook()


class UnstableDict(dict):
    """
    A dict that fails to be listed, which is what a dict being inserted into by
    another thread does
    """

    def __iter__(self):
        raise RuntimeError('dictionary changed size during iteration')


class LoadRecorder:
    """
    Mixin that counts load_resource calls per file, with an optional delay to
    widen the race window of the concurrent tests
    """

    def __init__(self, delay=0.):
        super().__init__()
        self.delay = delay
        self.calls = {}
        self._calls_lock = threading.Lock()

    def count_load(self, file):
        """
        Record one load of a file, and optionally take some time over it

        Args:
            file (str):
        """
        with self._calls_lock:
            self.calls[file] = self.calls.get(file, 0) + 1
        if self.delay:
            time.sleep(self.delay)


class RecordingCacheTTL(LoadRecorder, ResourceCacheTTL):
    def load_resource(self, file, **kwargs):
        self.count_load(file)
        return f'value:{file}'


class RecordingCache(LoadRecorder, ResourceCache):
    def load_resource(self, file, **kwargs):
        self.count_load(file)
        return f'value:{file}'


@pytest.fixture(params=[RecordingCacheTTL, RecordingCache], ids=['ttl', 'plain'])
def cache_cls(request):
    """
    Both cache classes share the get() contract
    """
    return request.param


class TestGet:
    def test_loads_once_and_returns_same_object(self, cache_cls):
        """
        The first get() loads the resource, later get() calls hit the cache and
        hand out the very same object
        """
        cache = cache_cls()
        value = cache.get('a')
        assert value == 'value:a'
        assert cache.get('a') is value
        assert cache.get('a') is value
        assert cache.calls == {'a': 1}

    def test_caches_each_file_independently(self, cache_cls):
        """
        The cache is keyed by file: every file is loaded once, whatever the
        order and the number of the requests
        """
        cache = cache_cls()
        values = {file: cache.get(file) for file in ['a', 'b', 'a', 'c', 'b', 'a']}
        assert values == {'a': 'value:a', 'b': 'value:b', 'c': 'value:c'}
        assert cache.calls == {'a': 1, 'b': 1, 'c': 1}

    def test_passes_kwargs_to_load_resource(self, cache_cls):
        """
        get() forwards its keyword arguments to load_resource(), while the
        entry is still keyed by the file only (a load resource may need more
        than the file to be built, the file is what identifies it)
        """
        class KwargCache(cache_cls):
            def load_resource(self, file, **kwargs):
                self.count_load(file)
                return (file, sorted(kwargs.items()))

        cache = KwargCache()
        assert cache.get('a', folder='x') == ('a', [('folder', 'x')])
        # cache hit: the arguments of the first load are the ones in use
        assert cache.get('a', folder='y') == ('a', [('folder', 'x')])
        assert cache.get('b', folder='y') == ('b', [('folder', 'y')])
        assert cache.calls == {'a': 1, 'b': 1}

    @pytest.mark.parametrize('value', [None, 0, '', False, [], {}])
    def test_caches_falsy_values(self, cache_cls, value):
        """
        A falsy resource is a cache hit like any other, it must not be loaded
        again (the cache is not allowed to use the truthiness of a value to
        tell a hit from a miss)
        """
        class ValueCache(cache_cls):
            def load_resource(self, file, **kwargs):
                self.count_load(file)
                return value

        cache = ValueCache()
        assert cache.get('a') is value
        assert cache.get('a') is value
        assert cache.calls == {'a': 1}

    @pytest.mark.parametrize('base_cls', [ResourceCacheTTL, ResourceCache], ids=['ttl', 'plain'])
    def test_load_resource_must_be_implemented(self, base_cls):
        """
        The base classes do not load anything, get() propagates the
        NotImplementedError and keeps no state behind
        """
        cache = base_cls()
        with pytest.raises(NotImplementedError):
            cache.get('a')
        assert cache._cache == {}
        assert dict(cache._lock) == {}

    def test_load_failure_does_not_poison_the_cache(self, cache_cls):
        """
        The caller of a failed get() sees the exception of load_resource() and
        the next get() tries again (a failed resource is not cached)
        """
        class AlwaysFailCache(cache_cls):
            def load_resource(self, file, **kwargs):
                self.count_load(file)
                raise FileNotFoundError(file)

        cache = AlwaysFailCache()
        for _ in range(3):
            with pytest.raises(FileNotFoundError):
                cache.get('a')
        assert cache._cache == {}
        assert cache.calls == {'a': 3}

    def test_removes_the_pre_resource_lock(self, cache_cls):
        """
        The pre-resource lock of a file is dropped once the resource is
        cached, a settled cache holds no lock at all
        """
        cache = cache_cls()
        for file in ['a', 'b', 'c']:
            cache.get(file)
        assert dict(cache._lock) == {}

    def test_releases_the_pre_resource_lock_when_load_fails(self, cache_cls):
        """
        A failed load must not leave the pre-resource lock behind either: the
        lock table would grow once per file that failed once. The next get()
        is free to retry.
        """
        class FailOnceCache(cache_cls):
            def __init__(self):
                super().__init__()
                self.fail = True

            def load_resource(self, file, **kwargs):
                self.count_load(file)
                if self.fail:
                    self.fail = False
                    raise FileNotFoundError(file)
                return f'value:{file}'

        cache = FailOnceCache()
        with pytest.raises(FileNotFoundError):
            cache.get('a')
        assert cache._cache == {}
        assert dict(cache._lock) == {}
        assert cache.get('a') == 'value:a'
        assert cache.calls == {'a': 2}
        assert dict(cache._lock) == {}


class TestResourceCacheTTLGet:
    def test_get_records_and_refreshes_last_use(self, clock):
        """
        A cache hit refreshes the last use of the entry (that is what keeps a
        resource in use alive), a cache miss does it while loading
        """
        cache = RecordingCacheTTL()
        cache.get('a')
        assert cache._last_use == {'a': 1000.}
        clock.shift(30)
        cache.get('a')
        assert cache._last_use == {'a': 1030.}
        clock.shift(30)
        cache.get('b')
        assert cache._last_use == {'a': 1030., 'b': 1060.}
        assert cache.calls == {'a': 1, 'b': 1}


class TestGc:
    def test_released_resource_is_loaded_again(self, cache_cls, clock):
        """
        gc() releases the cached resources, a later get() builds them again
        """
        cache = cache_cls()
        cache.get('a')
        assert cache.calls == {'a': 1}
        # walk past the idle window of the TTL cache (60s by default)
        clock.shift(61)
        cache.gc()
        assert cache._cache == {}
        assert cache.get('a') == 'value:a'
        assert cache.calls == {'a': 2}


class TestResourceCacheTTLGc:
    def test_keeps_fresh_entries(self, clock):
        """
        An entry used inside the idle window survives gc()
        """
        cache = RecordingCacheTTL()
        cache.get('a')
        clock.shift(59)
        cache.gc()
        assert cache._cache == {'a': 'value:a'}
        assert cache._last_use == {'a': 1000.}
        assert cache.calls == {'a': 1}

    def test_immune_to_a_wall_clock_jump(self, monkeypatch):
        """
        The idle window is measured on a monotonic clock: a jump of the wall
        clock (NTP correction, system time changed by the user) must not
        release the resources that are in use
        """
        cache = RecordingCacheTTL()
        assert cache.get('a') == 'value:a'
        real_time = time.time
        # the wall clock jumps one hour forward, the monotonic clock does not
        monkeypatch.setattr(time, 'time', lambda: real_time() + 3600)
        cache.gc(idle=60)
        assert cache._cache == {'a': 'value:a'}
        assert cache.calls == {'a': 1}

    @pytest.mark.parametrize('advance, released', [
        # the idle window is exclusive: used exactly `idle` seconds ago is idle
        (59, False),
        (60, True),
        (61, True),
    ])
    def test_idle_boundary(self, clock, advance, released):
        """
        gc() releases the entries that were not used for more than 60s
        """
        cache = RecordingCacheTTL()
        cache.get('a')
        clock.shift(advance)
        cache.gc()
        if released:
            assert cache._cache == {}
            assert cache._last_use == {}
        else:
            assert cache._cache == {'a': 'value:a'}
            assert cache._last_use == {'a': 1000.}
        assert cache.calls == {'a': 1}

    def test_releases_only_the_idle_entries(self, clock):
        """
        gc() walks every entry and releases the idle ones only
        """
        cache = RecordingCacheTTL()
        cache.get('old')
        clock.shift(50)
        cache.get('fresh')
        clock.shift(20)
        cache.gc(idle=60)
        assert cache._cache == {'fresh': 'value:fresh'}
        assert cache._last_use == {'fresh': 1050.}
        assert cache.calls == {'old': 1, 'fresh': 1}

    def test_get_refreshes_the_idle_deadline(self, clock):
        """
        A resource used again inside the idle window is not released, even if
        it was loaded long before
        """
        cache = RecordingCacheTTL()
        cache.get('a')
        clock.shift(50)
        cache.get('a')
        clock.shift(50)
        # 100s after the load, but only 50s after the last use
        cache.gc(idle=60)
        assert cache._cache == {'a': 'value:a'}
        assert cache._last_use == {'a': 1050.}
        assert cache.calls == {'a': 1}

    def test_gc_on_empty_cache(self, clock):
        """
        gc() of a cache that holds nothing does nothing
        """
        cache = RecordingCacheTTL()
        cache.gc()
        cache.gc(idle=0)
        assert cache._cache == {}
        assert cache._last_use == {}

    def test_releases_entry_without_last_use(self, clock):
        """
        An entry without a last use is an orphan cache, gc() treats it as
        outdated and leaves no half state behind
        """
        cache = RecordingCacheTTL()
        cache.get('a')
        del cache._last_use['a']
        cache.gc(idle=0)
        assert cache._cache == {}
        assert cache._last_use == {}

    def test_does_not_evict_the_entry_that_is_being_published(self, clock):
        """
        An entry is only visible to gc() once its last use is recorded:
        a gc() that runs while an entry is published must see it as fresh
        instead of releasing it (a resource that was just loaded would then be
        loaded again on the next get, and the timestamp would be lost)
        """
        cache = RecordingCacheTTL()
        hooked = HookedDict()
        cache._cache = hooked
        hooked.hook = lambda: cache.gc(idle=0.5)
        assert cache.get('a') == 'value:a'
        # the entry is cached: the next get() is a hit
        assert cache.get('a') == 'value:a'
        assert cache.calls == {'a': 1}
        assert set(cache._last_use) == set(cache._cache)

    def test_survives_cache_mutation(self, clock):
        """
        A RuntimeError of listing a dict that another thread is inserting into
        must not escape gc(), the next gc() call does the job
        """
        cache = RecordingCacheTTL()
        cache.get('a')
        cache._cache = UnstableDict(cache._cache)
        cache.gc(idle=0)
        assert dict(cache._cache) == {'a': 'value:a'}
        assert cache._last_use == {'a': 1000.}


class TestResourceCacheGc:
    def test_gc_clears_all_entries(self):
        """
        gc() releases every entry at once, the next get() builds them again
        """
        cache = RecordingCache()
        cache.get('a')
        cache.get('b')
        cache.gc()
        assert cache._cache == {}
        assert cache.calls == {'a': 1, 'b': 1}
        assert cache.get('a') == 'value:a'
        assert cache.calls == {'a': 2, 'b': 1}

    def test_gc_on_empty_cache(self):
        """
        gc() of a cache that holds nothing does nothing
        """
        cache = RecordingCache()
        cache.gc()
        assert cache._cache == {}

    def test_gc_does_not_lose_a_load_in_flight(self):
        """
        A resource that is being loaded while gc() clears the cache is still
        delivered to its caller and is still the cached one afterwards
        """

        class GatedCache(RecordingCache):
            def __init__(self):
                super().__init__()
                self.entered = threading.Event()
                self.resume = threading.Event()

            def load_resource(self, file, **kwargs):
                self.count_load(file)
                self.entered.set()
                self.resume.wait(timeout=5)
                return f'value:{file}'

        cache = GatedCache()
        results = []
        loader = threading.Thread(target=lambda: results.append(cache.get('a')), daemon=True)
        loader.start()
        assert cache.entered.wait(timeout=5)
        # nothing is cached yet, clear the cache while the load is in flight
        cache.gc()
        cache.resume.set()
        loader.join(timeout=5)
        assert not loader.is_alive()
        assert results == ['value:a']
        # the value that was produced after the clear is the cached one
        assert cache.get('a') == 'value:a'
        assert cache.calls == {'a': 1}


class TestConcurrentGet:
    def test_single_load_per_file(self, cache_cls):
        """
        Concurrent get() calls of the same file trigger exactly one load and
        every caller receives the same object
        """
        cache = cache_cls(delay=0.001)
        results = []
        barrier = threading.Barrier(8)

        def worker():
            barrier.wait(timeout=5)
            results.append(cache.get('a'))

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert not any(thread.is_alive() for thread in threads)
        assert len(results) == 8
        assert cache.calls == {'a': 1}
        assert len({id(value) for value in results}) == 1
        assert dict(cache._lock) == {}

    def test_single_load_per_file_of_many_files(self, cache_cls):
        """
        Contention on many files at once: each file is loaded exactly once and
        every caller gets the value of its own file
        """
        files = [f'file{i}' for i in range(8)]
        cache = cache_cls(delay=0.001)
        results = {}
        results_lock = threading.Lock()
        barrier = threading.Barrier(16)

        def worker(file):
            barrier.wait(timeout=5)
            value = cache.get(file)
            with results_lock:
                results.setdefault(file, []).append(value)

        threads = [threading.Thread(target=worker, args=(file,), daemon=True) for file in files for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert not any(thread.is_alive() for thread in threads)
        assert cache.calls == {file: 1 for file in files}
        assert results == {file: [f'value:{file}'] * 2 for file in files}
        assert dict(cache._lock) == {}

    def test_slow_file_does_not_block_the_other_files(self, cache_cls):
        """
        The pre-resource lock is per file: a file that is being loaded does not
        hold back the other files
        """

        class GatedCache(cache_cls):
            def __init__(self):
                super().__init__()
                self.entered = threading.Event()
                self.resume = threading.Event()

            def load_resource(self, file, **kwargs):
                self.count_load(file)
                if file == 'a':
                    self.entered.set()
                    self.resume.wait(timeout=5)
                return f'value:{file}'

        cache = GatedCache()
        results = []
        loader = threading.Thread(target=lambda: results.append(cache.get('a')), daemon=True)
        loader.start()
        assert cache.entered.wait(timeout=5)
        other = threading.Thread(target=lambda: results.append(cache.get('b')), daemon=True)
        other.start()
        other.join(timeout=5)
        assert not other.is_alive(), 'loading a file must not wait for another file'
        cache.resume.set()
        loader.join(timeout=5)
        assert not loader.is_alive()
        assert sorted(results) == ['value:a', 'value:b']
        assert cache.calls == {'a': 1, 'b': 1}


class TestConcurrentGc:
    def test_ttl_gc_with_concurrent_getters(self, clock):
        """
        gc() running while other threads get(): no exception, every caller gets
        the value of its file, and a settled cache keeps no leftover state
        """
        files = [f'file{i}' for i in range(4)]
        cache = RecordingCacheTTL()
        errors = []
        stop = threading.Event()

        def gc_worker():
            while not stop.is_set():
                cache.gc(idle=0)

        def get_worker():
            # collect instead of assert: an exception of a worker thread would
            # not fail the test on its own
            try:
                for _ in range(50):
                    for file in files:
                        value = cache.get(file)
                        if value != f'value:{file}':
                            errors.append(value)
            except Exception as e:
                errors.append(e)

        gcs = [threading.Thread(target=gc_worker, daemon=True) for _ in range(2)]
        gets = [threading.Thread(target=get_worker, daemon=True) for _ in range(4)]
        for thread in gets + gcs:
            thread.start()
        for thread in gets:
            thread.join(timeout=30)
        stop.set()
        for thread in gcs:
            thread.join(timeout=5)
        assert not any(thread.is_alive() for thread in gets + gcs)
        assert errors == []
        # the pre-resource locks are all released
        assert dict(cache._lock) == {}
        # nothing is left in the cache once every entry was idle for 0s
        cache.gc(idle=0)
        assert cache._cache == {}
        assert cache._last_use == {}
        # and the cache still works
        assert cache.get('a') == 'value:a'

    def test_plain_gc_with_concurrent_getters(self):
        """
        The same for the plain cache, whose gc() clears everything
        """
        files = [f'file{i}' for i in range(4)]
        cache = RecordingCache()
        errors = []
        stop = threading.Event()

        def gc_worker():
            while not stop.is_set():
                cache.gc()

        def get_worker():
            try:
                for _ in range(50):
                    for file in files:
                        value = cache.get(file)
                        if value != f'value:{file}':
                            errors.append(value)
            except Exception as e:
                errors.append(e)

        gcs = [threading.Thread(target=gc_worker, daemon=True) for _ in range(2)]
        gets = [threading.Thread(target=get_worker, daemon=True) for _ in range(4)]
        for thread in gets + gcs:
            thread.start()
        for thread in gets:
            thread.join(timeout=30)
        stop.set()
        for thread in gcs:
            thread.join(timeout=5)
        assert not any(thread.is_alive() for thread in gets + gcs)
        assert errors == []
        assert dict(cache._lock) == {}
        cache.gc()
        assert cache._cache == {}
        assert cache.get('a') == 'value:a'
