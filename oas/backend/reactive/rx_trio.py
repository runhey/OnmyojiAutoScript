import contextvars
import weakref
from typing import Any, Callable, Generator, Generic, TypeVar

import trio

from oas.backend.reactive.not_found import _NOT_FOUND

T = TypeVar('T')


class ReactiveContext:
    """
    Global context for tracking dependencies during computation.
    """
    _local = contextvars.ContextVar('observer', default=None)

    @classmethod
    def get_observer(cls):
        """
        Returns:
            tuple[Any, str] | None: (weak_ref_to_object, property_name)
        """
        return cls._local.get()

    @classmethod
    def set_observer(cls, observer):
        """
        Args:
            observer (tuple[Any, str] | None): (weak_ref_to_object, property_name)
        """
        cls._local.set(observer)


class AwaitableProperty(Generic[T]):
    def __init__(self, reactive_deco: "async_reactive[T]", obj):
        """
        A meaning less wrapper to make `await` happy,
        so you can use:
            await <ClassName>.<property_name>
        """
        self.reactive_deco = reactive_deco
        self.obj = obj

    def __await__(self) -> Generator[Any, Any, T]:
        """
        Allows usage: state = await self.prop
        """
        return self.reactive_deco.get_value(self.obj).__await__()

    async def mutate(self, new=_NOT_FOUND):
        """
        Allows usage: await self.prop.mutate() or await self.prop.mutate(new_value)

        This proxies the call to the descriptor's mutate method,
        automatically passing the bound instance (self.obj).
        """
        await self.reactive_deco.mutate(self.obj, new)


class async_reactive(Generic[T]):
    def __init__(self, func: Callable[..., T]):
        self.func = func
        self.name = func.__name__
        self.cache_attr = f'_reactive_cache_{self.name}'

        # Track observers: {weak_ref_to_object, set(property_name)}
        self.observers: "weakref.WeakKeyDictionary[object, set[str]]" = weakref.WeakKeyDictionary()
        # Lock computation and observer changes
        self.lock = trio.Lock()

    def __get__(self, obj, cls=None):
        """
        __get__ is separated into get_value() and AwaitableProperty,
        so you can use:
            await <ClassName>.<property_name>
        """
        if obj is None:
            return self

        return AwaitableProperty(self, obj)

    async def get_value(self, obj) -> T:
        # return cache if available
        cache = getattr(obj, self.cache_attr, _NOT_FOUND)
        if cache is not _NOT_FOUND:
            # register observer
            parent = ReactiveContext.get_observer()
            if parent is not None and parent != (obj, self.name):
                parent_obj, parent_name = parent
                await self._observer_add(parent_obj, parent_name)
            return cache

        async with self.lock:
            # another thread may have computed while we are waiting for lock
            cache = getattr(obj, self.cache_attr, _NOT_FOUND)
            if cache is not _NOT_FOUND:
                # register observer
                parent = ReactiveContext.get_observer()
                if parent is not None and parent != (obj, self.name):
                    parent_obj, parent_name = parent
                    self._observer_add_unsafe(parent_obj, parent_name)
                return cache
            # compute the value
            value = await self.compute(obj)
            setattr(obj, self.cache_attr, value)
            return value

    def __set__(self, obj, value):
        raise ValueError('You should not set value to a reactive object, that would break the observation chain. '
                         'Set value to reactive_source object instead')

    async def compute(self, obj):
        """
        Compute value, assumes lock is held
        """
        parent = ReactiveContext.get_observer()
        # enter new context, so dependencies can know who's observing
        current = (obj, self.name)
        ReactiveContext.set_observer(current)
        try:
            # call
            value = await self.func(obj)

            # register observer
            if parent is not None and parent != (obj, self.name):
                parent_obj, parent_name = parent
                self._observer_add_unsafe(parent_obj, parent_name)

            return value

        finally:
            # rollback context
            ReactiveContext.set_observer(parent)

    async def _observer_add(self, obj, name):
        """
        Add an observer to property

        Args:
            obj (Any):
            name: property_name
        """
        async with self.lock:
            self._observer_add_unsafe(obj, name)

    def _observer_add_unsafe(self, obj, name):
        """
        Add an observer to property, assumes lock is held

        Args:
            obj (Any):
            name: property_name
        """
        if obj in self.observers:
            observer_names = self.observers[obj]
        else:
            observer_names = set()
            self.observers[obj] = observer_names

        observer_names.add(name)

    async def _broadcast_observer(self, obj, observer_items, old, new):
        async with trio.open_nursery() as nursery:
            # Broadcast changes to external function
            if isinstance(obj, AsyncReactiveCallback):
                nursery.start_soon(obj.reactive_callback, self.name, old, new)

            # Notify observers outside the lock to prevent deadlocks
            for observer_obj, names in observer_items:
                observer_cls = observer_obj.__class__
                for name in names:
                    observer_reactive = getattr(observer_cls, name, _NOT_FOUND)
                    if observer_reactive is not _NOT_FOUND:
                        try:
                            broadcast = observer_reactive.broadcast
                        except AttributeError:
                            # this shouldn't happen
                            continue
                        nursery.start_soon(broadcast, observer_obj)

    async def broadcast(self, obj, old=_NOT_FOUND, new=_NOT_FOUND):
        """
        Broadcast changes to all observers

        Args:
            obj: ReactiveCallback instance, or any instance
            old: Old value of the reactive data
                If `old` is _NOT_FOUND, get `old` from `self.cache_attr`
            new: New value of the reactive data
                If `new` is _NOT_FOUND, compute reactive agin
        """
        # Get observers copy under lock, then notify outside lock
        async with self.lock:
            if old is _NOT_FOUND:
                old = getattr(obj, self.cache_attr, _NOT_FOUND)
            if new is _NOT_FOUND:
                new = await self.compute(obj)
                setattr(obj, self.cache_attr, new)
            observer_items = list(self.observers.items())

        # Check if value changed
        if new is _NOT_FOUND:
            # this shouldn't happen
            return
        if old == new:
            # value unchanged
            return

        await self._broadcast_observer(obj, observer_items, old, new)

    async def mutate(self, obj, new=_NOT_FOUND):
        """
        Manually triggers a broadcast for this reactive property on a specific instance.
        Current value will be broadcast to all observers as `new`,
        `old` is always _NOT_FOUND because value is already changed by in-place mutation.

        Args:
            obj: The instance on which to trigger the broadcast.
            new: New value of the reactive data
                If `new` is _NOT_FOUND, reuse current data

        Usage:
            <ClassName>.<property_name>.mutate(<instance_of_class>)

        Examples:
            processor = DeepDataProcessor()
            # this won't trigger any broadcast because it's an in-place mutation
            processor.raw_data['user']['profile']['name'] = 'Bob'
            # this would broadcast changes to all observers
            DeepDataProcessor.raw_data.mutate(processor)
        """
        # Get observers copy under lock, then notify outside lock
        async with self.lock:
            if new is _NOT_FOUND:
                new = getattr(obj, self.cache_attr, _NOT_FOUND)
            else:
                setattr(obj, self.cache_attr, new)
            observer_items = list(self.observers.items())

        # Check if value changed
        if new is _NOT_FOUND:
            # this shouldn't happen
            return

        await self._broadcast_observer(obj, observer_items, _NOT_FOUND, new)


class async_reactive_source(async_reactive):
    async def compute(self, obj):
        """
        Compute value, assumes lock is held
        reactive_source should not observe anything, so here just register observer, no new context
        """
        parent = ReactiveContext.get_observer()

        # call
        value = await self.func(obj)

        # register observer
        if parent is not None and parent != (obj, self.name):
            parent_obj, parent_name = parent
            self._observer_add_unsafe(parent_obj, parent_name)

        return value

    def __set__(self, obj, value):
        raise TypeError(
            f'You should not set an async reactive source synchronously. '
            f'Use "await self.{self.name}.mutate(value)" instead.'
        )


class async_reactive_nocache(async_reactive):
    async def get_value(self, obj) -> T:
        return await self.compute(obj)

    async def broadcast(self, obj, old=_NOT_FOUND, new=_NOT_FOUND):
        """
        No-cache side-effect carrier: nothing to invalidate and nothing to
        compare (the cache is never written, so old is always _NOT_FOUND) -
        just re-run the side effect, then notify observers as the base
        class does (normally none for a side-effect carrier).

        The base-class implementation computes inside the descriptor lock.
        That lock is shared by every instance of the descriptor -- all topic
        instances share BaseTopic._resubscribe, so one slow round (a full
        view build inside subscribe) would serialize the broadcasts of
        every connection and block their mutate() calls. Serialization of
        the side effect is the caller's per-instance job
        (BaseTopic._resubscribe busy/dirty merging); concurrent instances
        are independent and need no mutual exclusion.
        """
        new = await self.compute(obj)
        async with self.lock:
            observer_items = list(self.observers.items())
        await self._broadcast_observer(obj, observer_items, _NOT_FOUND, new)

    async def mutate(self, obj, new=_NOT_FOUND):
        """
        Mutate without setting cache
        """
        # Get observers copy under lock, then notify outside lock
        async with self.lock:
            if new is _NOT_FOUND:
                new = await self.compute(obj)
            observer_items = list(self.observers.items())

        # Check if value changed
        if new is _NOT_FOUND:
            # this shouldn't happen
            return

        await self._broadcast_observer(obj, observer_items, _NOT_FOUND, new)


class AsyncReactiveCallback:
    async def reactive_callback(self, name, old, new):
        """
        If any reactive value from this object is changed, this method will be called
        Note that `old` is always _NOT_FOUND because value is already changed by in-place mutation.
        """
        pass
