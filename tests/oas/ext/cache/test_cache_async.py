import asyncio
import inspect

import pytest
import trio

from oas.ext.cache.cache import InstanceCacheOperation
from oas.ext.cache.cache_async import (
    AsyncCacheOperation, AwaitableResult, cached_property_async, cached_property_async_asyncio_lock,
    cached_property_async_trio_lock
)


def drive(coro):
    """
    Run a coroutine to completion without any event loop.

    A coroutine that only awaits AwaitableResult objects never yields, so it finishes
    on the first send() and returns the value carried by the StopIteration.

    Args:
        coro: The coroutine to run

    Returns:
        The returned value of the coroutine
    """
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value
    raise AssertionError("coroutine did not finish on the first send()")


class MockAsyncInstance:
    def __init__(self):
        self.count = 0
        self.slow_count = 0
        self.fail_count = 0

    @cached_property_async
    async def value(self):
        self.count += 1
        return f"value_{self.count}"

    @cached_property_async
    async def slow_value(self):
        # suspends, so a concurrent await can not reuse the calculation
        await asyncio.sleep(0)
        self.slow_count += 1
        return f"slow_{self.slow_count}"

    @cached_property_async
    async def unstable_value(self):
        self.fail_count += 1
        if self.fail_count == 1:
            raise ValueError("calculation failed")
        return f"unstable_{self.fail_count}"


class MockTrioLockInstance:
    def __init__(self):
        self.count = 0

    @cached_property_async_trio_lock
    async def value(self):
        self.count += 1
        # suspend, so a concurrent await overlaps the calculation
        await trio.sleep(0)
        return f"value_{self.count}"


class MockAsyncioLockInstance:
    def __init__(self):
        self.count = 0
        self.fail_count = 0

    @cached_property_async_asyncio_lock
    async def value(self):
        self.count += 1
        # suspend, so a concurrent await overlaps the calculation
        await asyncio.sleep(0)
        return f"value_{self.count}"

    @cached_property_async_asyncio_lock
    async def failing_value(self):
        self.fail_count += 1
        await asyncio.sleep(0)
        raise ValueError("calculation failed")


class TestAwaitableResult:
    def test_await_value(self):
        async def coro():
            return await AwaitableResult(9527)

        assert drive(coro()) == 9527

    def test_await_none(self):
        async def coro():
            return await AwaitableResult(None)

        assert drive(coro()) is None

    def test_await_multiple_times(self):
        result = AwaitableResult("value")

        async def coro():
            first = await result
            second = await result
            return first, second

        assert drive(coro()) == ("value", "value")

    @pytest.mark.parametrize("value, expected", [
        (9527, "<AwaitableResult: 9527>"),
        ("9527", "<AwaitableResult: '9527'>"),
        (None, "<AwaitableResult: None>"),
    ])
    def test_repr(self, value, expected):
        assert repr(AwaitableResult(value)) == expected

    def test_await_asyncio(self):
        result = AwaitableResult(9527)

        async def coro():
            return await result

        # the result is not bound to an event loop, any loop can await it
        assert asyncio.run(coro()) == 9527
        assert asyncio.run(coro()) == 9527

    @pytest.mark.trio
    async def test_await_trio(self):
        result = AwaitableResult(9527)
        assert await result == 9527
        assert await result == 9527


class TestAsyncCacheOperation:
    def test_set(self):
        obj = MockAsyncInstance()
        AsyncCacheOperation.set(obj, "value", "manual_value")

        # the value is wrapped, so the property is still awaitable
        assert isinstance(obj.__dict__["value"], AwaitableResult)
        assert AsyncCacheOperation.get(obj, "value") is obj.__dict__["value"]

        async def coro():
            return await obj.value

        assert drive(coro()) == "manual_value"
        # the coroutine function was never called
        assert obj.count == 0

    def test_replace(self):
        obj = MockAsyncInstance()

        # No cached value: old_default is returned and the new value is wrapped
        assert AsyncCacheOperation.replace(obj, "value", "first") is None
        assert isinstance(obj.__dict__["value"], AwaitableResult)

        # Cached value: the old value is unwrapped
        assert AsyncCacheOperation.replace(obj, "value", "second") == "first"

        async def coro():
            return await obj.value

        assert drive(coro()) == "second"
        # the coroutine function was never called
        assert obj.count == 0

    def test_set_no_dict(self):
        with pytest.raises(TypeError, match="No '__dict__' attribute"):
            AsyncCacheOperation.set(1, "any", "value")

    def test_has_get_pop(self):
        obj = MockAsyncInstance()
        assert AsyncCacheOperation.has(obj, "value") is False
        assert AsyncCacheOperation.get(obj, "value") is None

        AsyncCacheOperation.set(obj, "value", "manual_value")
        assert AsyncCacheOperation.has(obj, "value") is True
        assert isinstance(AsyncCacheOperation.get(obj, "value"), AwaitableResult)

        popped = AsyncCacheOperation.pop(obj, "value")
        assert isinstance(popped, AwaitableResult)
        assert AsyncCacheOperation.has(obj, "value") is False

    def test_warm_is_coroutine(self):
        # warmup must be a coroutine, so that the value can be calculated
        assert inspect.iscoroutinefunction(AsyncCacheOperation.warm)
        assert inspect.iscoroutinefunction(cached_property_async.warm)

    def test_sync_warm_returns_false(self):
        obj = MockAsyncInstance()
        # the sync warmup can't calculate an async property, so it reports failure
        assert InstanceCacheOperation.warm(obj, "value") is False
        assert cached_property_async.has(obj, "value") is False
        assert obj.count == 0

    def test_warm(self):
        obj = MockAsyncInstance()
        assert cached_property_async.has(obj, "value") is False

        assert drive(cached_property_async.warm(obj, "value")) is True
        assert cached_property_async.has(obj, "value") is True
        assert obj.count == 1

        # already warmup
        assert drive(cached_property_async.warm(obj, "value")) is True
        assert obj.count == 1

        async def coro():
            return await obj.value

        # the warmed value is returned without calculating again
        assert drive(coro()) == "value_1"
        assert obj.count == 1

    def test_warm_missing_attribute(self):
        obj = MockAsyncInstance()
        assert drive(cached_property_async.warm(obj, "non_existent")) is False

    def test_warm_no_dict(self):
        assert drive(cached_property_async.warm(1, "any")) is False

    def test_warm_not_a_descriptor(self):
        class Foo:
            value = 1

        assert drive(cached_property_async.warm(Foo(), "value")) is False

    def test_warm_inheritance(self):
        class Parent:
            def __init__(self):
                self.parent_count = 0

            @cached_property_async
            async def parent_value(self):
                self.parent_count += 1
                return "parent"

        class Child(Parent):
            def __init__(self):
                super().__init__()
                self.child_count = 0

            @cached_property_async
            async def child_value(self):
                self.child_count += 1
                return "child"

        obj = Child()
        assert drive(cached_property_async.warm(obj, "parent_value")) is True
        assert obj.parent_count == 1
        assert cached_property_async.has(obj, "parent_value") is True

        assert drive(cached_property_async.warm(obj, "child_value")) is True
        assert obj.child_count == 1
        assert cached_property_async.has(obj, "child_value") is True

    @pytest.mark.trio
    async def test_warm_trio(self):
        obj = MockAsyncInstance()
        assert await cached_property_async.warm(obj, "value") is True
        assert await obj.value == "value_1"
        assert obj.count == 1


class TestCachedPropertyAsync:
    def test_lazy_calculation(self):
        obj = MockAsyncInstance()
        # accessing the property does not calculate the value
        pending = obj.value
        assert hasattr(pending, "__await__")
        assert obj.count == 0
        assert cached_property_async.has(obj, "value") is False

    def test_await_without_event_loop(self):
        obj = MockAsyncInstance()

        async def coro():
            return await obj.value

        # no event loop at all, the value is calculated on the first send()
        assert drive(coro()) == "value_1"
        assert obj.count == 1

    def test_cache_after_await(self):
        obj = MockAsyncInstance()

        async def coro():
            return await obj.value

        assert drive(coro()) == "value_1"
        # cached as an AwaitableResult
        assert isinstance(obj.__dict__["value"], AwaitableResult)
        assert cached_property_async.has(obj, "value") is True
        # the cached awaitable is returned on every access
        assert obj.value is obj.__dict__["value"]
        # second await returns the cached value without calculating again
        assert drive(coro()) == "value_1"
        assert obj.count == 1

    def test_pending_awaitable_is_reusable(self):
        obj = MockAsyncInstance()
        pending = obj.value

        async def coro():
            return await pending

        assert drive(coro()) == "value_1"
        # the pending awaitable reuses the value cached by the first await
        assert drive(coro()) == "value_1"
        assert obj.count == 1

    def test_pending_awaitable_reuses_set_value(self):
        obj = MockAsyncInstance()
        pending = obj.value
        AsyncCacheOperation.set(obj, "value", "manual_value")

        async def coro():
            return await pending

        # the pending awaitable reuses the value set manually
        assert drive(coro()) == "manual_value"
        assert obj.count == 0

    def test_calculate_after_pop(self):
        obj = MockAsyncInstance()

        async def coro():
            return await obj.value

        assert drive(coro()) == "value_1"

        cached = cached_property_async.pop(obj, "value")
        assert isinstance(cached, AwaitableResult)
        assert cached_property_async.get(obj, "value") is None

        assert drive(coro()) == "value_2"
        assert obj.count == 2

    def test_exception_is_not_cached(self):
        obj = MockAsyncInstance()

        async def coro():
            return await obj.unstable_value

        with pytest.raises(ValueError, match="calculation failed"):
            drive(coro())
        assert cached_property_async.has(obj, "unstable_value") is False
        assert obj.fail_count == 1
        # calculated again on the next await
        assert drive(coro()) == "unstable_2"
        assert obj.fail_count == 2

    def test_class_access(self):
        assert isinstance(MockAsyncInstance.value, cached_property_async)
        # the descriptor inherits the async helpers, e.g. the coroutine warm()
        assert isinstance(MockAsyncInstance.value, AsyncCacheOperation)

    def test_slots_error(self):
        class SlotsWithCachedAsync:
            __slots__ = ("_val",)

            @cached_property_async
            async def val(self):
                return 1

        obj = SlotsWithCachedAsync()
        with pytest.raises(TypeError, match="No '__dict__' attribute"):
            _ = obj.val

    def test_await_asyncio(self):
        obj = MockAsyncInstance()

        async def coro():
            return await obj.value

        # the cached value is not bound to the event loop it was calculated on
        assert asyncio.run(coro()) == "value_1"
        assert asyncio.run(coro()) == "value_1"
        assert obj.count == 1

    def test_await_asyncio_concurrently(self):
        obj = MockAsyncInstance()

        async def coro():
            # the calculation never suspends, so only the first await calculates
            return await asyncio.gather(obj.value, obj.value, obj.value)

        assert asyncio.run(coro()) == ["value_1", "value_1", "value_1"]
        assert obj.count == 1

    def test_concurrent_first_await_is_not_deduplicated(self):
        obj = MockAsyncInstance()

        async def coro():
            return await asyncio.gather(obj.slow_value, obj.slow_value)

        # the calculation suspends, so both awaits calculate the value,
        # same as the plain cached_property does under threads
        assert sorted(asyncio.run(coro())) == ["slow_1", "slow_2"]
        assert obj.slow_count == 2

        async def coro_cached():
            return await obj.slow_value

        # the cache keeps one of the calculated values, it is not calculated again
        assert asyncio.run(coro_cached()) in ("slow_1", "slow_2")
        assert obj.slow_count == 2

    @pytest.mark.trio
    async def test_await_trio(self):
        obj = MockAsyncInstance()
        assert await obj.value == "value_1"
        assert await obj.value == "value_1"
        assert obj.count == 1

    @pytest.mark.trio
    async def test_await_trio_concurrently(self):
        obj = MockAsyncInstance()
        results = []

        async def worker():
            results.append(await obj.value)

        async with trio.open_nursery() as nursery:
            for _ in range(3):
                nursery.start_soon(worker)

        assert results == ["value_1", "value_1", "value_1"]
        assert obj.count == 1

    @pytest.mark.trio
    async def test_cached_value_is_not_bound_to_a_framework(self):
        obj = MockAsyncInstance()

        async def coro():
            return await obj.value

        # calculated without any event loop
        assert drive(coro()) == "value_1"
        # and the cached value can be awaited under trio
        assert await obj.value == "value_1"
        assert obj.count == 1


class TestCachedPropertyAsyncLock:
    def test_lazy_imports(self):
        # asyncio and trio are imported on the first await, not at module import
        import oas.ext.cache.cache_async as module
        assert not hasattr(module, "asyncio")
        assert not hasattr(module, "trio")

    def test_asyncio_deduplicates_concurrent_first_await(self):
        obj = MockAsyncioLockInstance()

        async def coro():
            return await asyncio.gather(obj.value, obj.value, obj.value)

        # only the first await calculates, the others reuse the calculated value
        assert asyncio.run(coro()) == ["value_1", "value_1", "value_1"]
        assert obj.count == 1
        # the lock is dropped after the calculation
        assert "_cached_property_lock_for_value" not in obj.__dict__

    def test_asyncio_reuses_cached_value(self):
        obj = MockAsyncioLockInstance()

        async def coro():
            return await obj.value

        assert asyncio.run(coro()) == "value_1"
        # the cached value is not bound to the loop that calculated it
        assert asyncio.run(coro()) == "value_1"
        assert obj.count == 1

    def test_asyncio_deduplicates_after_pop(self):
        obj = MockAsyncioLockInstance()

        async def coro():
            return await asyncio.gather(obj.value, obj.value)

        assert asyncio.run(coro()) == ["value_1", "value_1"]
        cached_property_async_asyncio_lock.pop(obj, "value")

        # recalculate once, and deduplicate the concurrent first awaits again
        assert asyncio.run(coro()) == ["value_2", "value_2"]
        assert obj.count == 2

    def test_asyncio_exception_releases_the_lock(self):
        obj = MockAsyncioLockInstance()

        async def worker():
            try:
                await obj.failing_value
            except ValueError:
                return "failed"
            return "ok"

        async def coro():
            return await asyncio.gather(worker(), worker())

        assert asyncio.run(coro()) == ["failed", "failed"]
        # the failed calculation is not cached, the waiters retry it one by one
        assert obj.fail_count == 2
        assert "_cached_property_lock_for_failing_value" in obj.__dict__
        # the lock is released, the next await retries the calculation
        assert asyncio.run(worker()) == "failed"
        assert obj.fail_count == 3

    def test_asyncio_sync_warm_returns_false(self):
        obj = MockAsyncioLockInstance()
        # the sync warmup can't calculate an async property
        assert InstanceCacheOperation.warm(obj, "value") is False
        assert cached_property_async_asyncio_lock.has(obj, "value") is False
        assert obj.count == 0

    @pytest.mark.trio
    async def test_trio_deduplicates_concurrent_first_await(self):
        obj = MockTrioLockInstance()
        results = []

        async def worker():
            results.append(await obj.value)

        async with trio.open_nursery() as nursery:
            for _ in range(3):
                nursery.start_soon(worker)

        # only the first await calculates, the others reuse the calculated value
        assert results == ["value_1", "value_1", "value_1"]
        assert obj.count == 1
        # the lock is dropped after the calculation
        assert "_cached_property_lock_for_value" not in obj.__dict__

    @pytest.mark.trio
    async def test_trio_reuses_cached_value(self):
        obj = MockTrioLockInstance()
        assert await obj.value == "value_1"
        assert await obj.value == "value_1"
        assert obj.count == 1

    @pytest.mark.trio
    async def test_trio_warm(self):
        obj = MockTrioLockInstance()
        assert await cached_property_async_trio_lock.warm(obj, "value") is True
        assert await obj.value == "value_1"
        assert obj.count == 1
