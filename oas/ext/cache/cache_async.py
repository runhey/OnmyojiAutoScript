from functools import wraps
from typing import Any, Awaitable, Callable, Generic, TypeVar

from .cache import InstanceCacheOperation

# Async cached property for coroutine functions, see cached_property_async.
# 1. **No event loop primitive**
# The calculated value is cached as an AwaitableResult, a fake awaitable that returns the value
# without yielding to the event loop. So it doesn't bind to asyncio or trio, the cached value can
# be awaited on any coroutine framework, on any event loop, or without any event loop at all, and
# unlike a coroutine or an asyncio.Future, it can be awaited multiple times.
# 2. **Not deduplicated**
# Like the plain cached_property under threads, concurrent first awaits of cached_property_async may calculate
# the value more than once, because waiting for a calculation in progress requires an event loop primitive.
# Use cached_property_async_asyncio_lock or cached_property_async_trio_lock to deduplicate them.
# 3. **No threadsafe version**
# A thread lock can't be held across an await, so there is no cached_property_async_threadsafe.

T = TypeVar('T')


class AwaitableResult(Generic[T]):
    """
    A fake awaitable that carries an already calculated value.

    Awaiting it never yields to the event loop, so no event loop is required to use it,
    and it works on any coroutine framework (asyncio, trio, ...). Unlike a coroutine or
    an asyncio.Future, it can be awaited multiple times.
    """

    __slots__ = ('_value',)

    def __init__(self, value: T):
        """
        Args:
            value (T): The value to return when awaited
        """
        self._value = value

    def __await__(self):
        """
        Returns:
            T: The value, returned without yielding to the event loop
        """
        # An unreachable yield, it makes this function a generator, so the await
        # protocol takes the value from its StopIteration and the caller is never
        # suspended. It is faster than making the result its own iterator.
        return self._value
        yield

    def __repr__(self):
        return f'<{type(self).__name__}: {self._value!r}>'


class AsyncCacheOperation(InstanceCacheOperation):
    """
    Helper functions to manage INSTANCE cached property of coroutine functions.

    Unlike InstanceCacheOperation, set() wraps the value into an AwaitableResult,
    and warm() is a coroutine, so that the value can be calculated on warmup.
    """

    # Tell the sync InstanceCacheOperation.warm() that the value can't be calculated synchronously
    calculated_on_await = True

    @staticmethod
    def set(instance, attrname, value):
        """
        Set a cached property on an INSTANCE.

        The value is wrapped into an AwaitableResult, so `await instance.attrname`
        returns it, the same as a calculated value.

        Args:
            instance:
            attrname (str):
            value:
        """
        InstanceCacheOperation.set(instance, attrname, AwaitableResult(value))

    @classmethod
    def replace(cls, instance, attrname, value, old_default=None):
        """
        Replace a cached property on an INSTANCE and return the old value.

        The old AwaitableResult is unwrapped, the new value is wrapped like
        set() does.

        Args:
            instance:
            attrname (str):
            value:
            old_default: Default to return if property never cached

        Returns:
            The old cached value, or old_default when the property was not cached
        """
        old = InstanceCacheOperation.get(instance, attrname, old_default)
        if isinstance(old, AwaitableResult):
            old = old._value
        cls.set(instance, attrname, value)
        return old

    @staticmethod
    async def warm(instance, attrname):
        """
        Warmup a cached property on an INSTANCE.

        Args:
            instance:
            attrname (str):

        Returns:
            bool: True if warmup or already warmup
                False if failed
        """
        try:
            if attrname in instance.__dict__:
                # already warmup
                return True
        except AttributeError:
            # No '__dict__' attribute
            return False

        # find descriptor
        cls = type(instance)
        descriptor = None
        for base in cls.__mro__:
            try:
                base_dict = base.__dict__
            except AttributeError:
                # No '__dict__' attribute
                continue
            descriptor = base_dict.get(attrname, None)
            if descriptor is not None:
                break
        if descriptor is None:
            return False

        # call __get__ function
        try:
            descriptor_get = descriptor.__get__
        except AttributeError:
            return False
        # calculate the value, it is cached when the await completes
        await descriptor_get(instance, cls)
        return attrname in instance.__dict__


class _PendingResult(Generic[T]):
    """
    The awaitable returned by cached_property_async when the value was never calculated.
    It calculates the value on await, then caches it into the instance.
    """

    __slots__ = ('_func', '_instance', '_attrname')

    def __init__(self, func, instance, attrname):
        """
        Args:
            func (Callable[[Any], Awaitable[T]]): Coroutine function of the cached property
            instance (object): Instance to calculate the value on
            attrname (str): Attribute name to cache the calculated value
        """
        self._func = func
        self._instance = instance
        self._attrname = attrname

    def __await__(self):
        """
        Returns:
            T: The calculated value
        """
        return self._calculate().__await__()

    async def _calculate(self):
        """
        Calculate the value, or reuse the value calculated by another await.

        Returns:
            T: The calculated value
        """
        instance = self._instance
        attrname = self._attrname
        cache = instance.__dict__
        # The value may have been calculated after this awaitable was created,
        # a pending awaitable is created on a cache miss
        if attrname in cache:
            return await cache[attrname]

        # calculate
        value = await self._func(instance)
        try:
            cache[attrname] = AwaitableResult(value)
        except TypeError:
            msg = (
                f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                f"does not support item assignment for caching {attrname!r} property."
            )
            raise TypeError(msg) from None
        return value


class _PendingResultLocked(_PendingResult):
    """
    The awaitable returned by the lock variants of cached_property_async.
    Unlike _PendingResult, concurrent first awaits wait for the calculation in
    progress with a framework lock, so the coroutine function is called once.
    """

    __slots__ = ('_lock_factory',)

    def __init__(self, func, instance, attrname, lock_factory):
        """
        Args:
            func (Callable[[Any], Awaitable[T]]): Coroutine function of the cached property
            instance (object): Instance to calculate the value on
            attrname (str): Attribute name to cache the calculated value
            lock_factory (Callable[[], Any]): Factory of the lock deduplicating concurrent first awaits
        """
        super().__init__(func, instance, attrname)
        self._lock_factory = lock_factory

    async def _calculate(self):
        """
        Calculate the value under the lock, or reuse the value calculated by another await.

        Returns:
            T: The calculated value
        """
        instance = self._instance
        attrname = self._attrname
        cache = instance.__dict__
        # The value may have been calculated after this awaitable was created,
        # a pending awaitable is created on a cache miss
        if attrname in cache:
            return await cache[attrname]

        # The lock is created and stored before the first await,
        # so other awaits can wait on it instead of calculating again
        lock_name = f'_cached_property_lock_for_{attrname}'
        lock = cache.get(lock_name, None)
        if lock is None:
            lock = self._lock_factory()
            cache[lock_name] = lock

        async with lock:
            # Double checked locking, the value may have been calculated
            # while this await was waiting for the lock
            if attrname in cache:
                value = await cache[attrname]
            else:
                value = await self._func(instance)
                try:
                    cache[attrname] = AwaitableResult(value)
                except TypeError:
                    msg = (
                        f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                        f"does not support item assignment for caching {attrname!r} property."
                    )
                    raise TypeError(msg) from None

            # cleanup, the lock will never be used again for this property on this instance
            try:
                del cache[lock_name]
            except KeyError:
                # this shouldn't happen
                pass
            return value


class cached_property_async(Generic[T], AsyncCacheOperation):
    """
    A high-performance, non-thread-safe cached property for coroutine functions.

    The coroutine function is called on the first `await instance.attr`, the calculated
    value is cached as an AwaitableResult, so later awaits return the cached value
    without calculating it again and without yielding to the event loop.

    It doesn't use any event loop primitive like Future or Task, so it works on any
    coroutine framework (asyncio, trio, ...). Meanwhile, like the plain cached_property
    under threads, concurrent first awaits may calculate the value more than once,
    use cached_property_async_asyncio_lock or cached_property_async_trio_lock to deduplicate them.

    Use the coroutine AsyncCacheOperation.warm() to calculate the value in advance,
    and AsyncCacheOperation.set() to set a value manually.
    """

    def __init__(self, func: Callable[[Any], "Awaitable[T]"]):
        self.func = func
        wraps(func)(self)

    def _create_pending_result(self, instance, attrname):
        """
        Create the awaitable that calculates the value on await.

        Args:
            instance (object):
            attrname (str):

        Returns:
            _PendingResult[T]:
        """
        return _PendingResult(self.func, instance, attrname)

    def __get__(self, instance, cls):
        """
        Args:
            instance (object): Instance that the property is accessed from,
                can be None if accessed from class.
            cls (type): The class that the property is accessed from.

        Returns:
            AwaitableResult[T]: The cached value, if the property was calculated before
            _PendingResult[T]: The awaitable that calculates the value, otherwise
        """
        if instance is None:
            return self

        attrname = self.func.__name__
        try:
            cache = instance.__dict__
        except AttributeError:
            # not all objects have __dict__ (e.g. class defines slots)
            msg = (
                f"No '__dict__' attribute on {type(instance).__name__!r} "
                f"instance to cache {attrname!r} property."
            )
            raise TypeError(msg) from None

        # check cache
        try:
            return cache[attrname]
        except KeyError:
            pass

        # calculate on await
        return self._create_pending_result(instance, attrname)


class cached_property_async_asyncio_lock(cached_property_async):
    """
    A cached_property_async that deduplicates concurrent first awaits on asyncio.

    The first await calculates the value while the others wait for the calculation
    in progress, so the coroutine function is called once. The lock is an asyncio.Lock
    that is created on the first await and dropped after the calculation, so this
    cached property must be used under asyncio until the value is cached, the cached
    value itself can be awaited on any coroutine framework.

    asyncio is imported on the first await, importing this module doesn't require it.
    """

    @staticmethod
    def _create_lock():
        """
        Create a lock of asyncio, it must be created inside a running event loop,
        as the lock binds the event loop on creation on python 3.8.

        Returns:
            asyncio.Lock:
        """
        # local import, the other cached properties don't require asyncio
        import asyncio
        return asyncio.Lock()

    def _create_pending_result(self, instance, attrname):
        """
        Args:
            instance (object):
            attrname (str):

        Returns:
            _PendingResultLocked[T]:
        """
        return _PendingResultLocked(self.func, instance, attrname, self._create_lock)


class cached_property_async_trio_lock(cached_property_async):
    """
    A cached_property_async that deduplicates concurrent first awaits on trio.

    The first await calculates the value while the others wait for the calculation
    in progress, so the coroutine function is called once. The lock is a trio.Lock
    that is created on the first await and dropped after the calculation, so this
    cached property must be used under trio until the value is cached, the cached
    value itself can be awaited on any coroutine framework.

    trio is imported on the first await, importing this module doesn't require it.
    """

    @staticmethod
    def _create_lock():
        """
        Create a lock of trio.

        Returns:
            trio.Lock:
        """
        # local import, trio is an optional dependency
        import trio
        return trio.Lock()

    def _create_pending_result(self, instance, attrname):
        """
        Args:
            instance (object):
            attrname (str):

        Returns:
            _PendingResultLocked[T]:
        """
        return _PendingResultLocked(self.func, instance, attrname, self._create_lock)
