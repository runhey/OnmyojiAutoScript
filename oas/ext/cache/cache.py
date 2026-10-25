from functools import wraps
from threading import Lock
from typing import Any, Callable, Generic, TypeVar

# cached_property in python is kind of a mess, it has 3 different cached_property function.
# - cached_property package, the original cached_property implementation before py3.8
# - functools.cached_property on py3.8+, the adopted cached_property
# - functools.cached_property on py3.12+, global lock is removed starting from 3.12
# So we deside to maintain our own cached_property to provide consistent behaviour among all python versions,
# and also keeping it fast, typed, thread-safe.
# 1. **Fast**
# our cached_property work as the original cached_property, the calculated value replace the
# cached_property function in __dict__. It's fast because at the second and later access it just a normal "obj.attr"
# access, while on py3.8+ and py3.12+ every access will go through __get__ method.
# 2. **Thread Safe**
# We separate another function threaded_cached_property, use it if you do care thread safety.
# On py3.8 every decorated function withs the same name share the lock resulting in bad performance.
# On py3.12 cached_property may be calculated twice on race condition.
# 3. **Async support**
# Don't decorate an async function with cached_property, it's not aware of await and would cache the coroutine
# object, which can only be awaited once. Use cached_property_async in cache_async.py instead, it calculates the
# value on the first `await obj.attr`, then caches the value as an AwaitableResult, so later awaits return the
# cached value without yielding to the event loop, working on any coroutine framework (asyncio, trio, ...).

T = TypeVar("T")


class CacheOperation:
    """
    Common base for all cached property operations
    """
    pass


class InstanceCacheOperation(CacheOperation):
    """
    Helper functions to manage INSTANCE cached property.
    """
    # True if the value is calculated on await, so it can't be warmed up synchronously,
    # set to True by AsyncCacheOperation, e.g. cached_property_async
    calculated_on_await = False

    @staticmethod
    def pop(instance, attrname, default=None):
        """
        Delete a cached property safely from an INSTANCE.

        Args:
            instance:
            attrname (str):
            default: Default to return if property never cached
        """
        try:
            d = instance.__dict__
            if attrname in d:
                return d.pop(attrname, default)
            return default
        except (AttributeError, TypeError):
            # No __dict__
            return default

    @staticmethod
    def has(instance, attrname):
        """
        Check if a property is cached on an INSTANCE.

        Args:
            instance:
            attrname (str):
        """
        try:
            return attrname in instance.__dict__
        except AttributeError:
            # No __dict__, just not exists
            return False

    @staticmethod
    def get(instance, attrname, default=None):
        """
        Get a potential cached property from an INSTANCE without calculating it.

        Args:
            instance:
            attrname (str):
            default: Default to return if property never cached
        """
        try:
            return instance.__dict__.get(attrname, default)
        except AttributeError:
            # No __dict__, just not exists
            return default

    @staticmethod
    def set(instance, attrname, value):
        """
        Set a cached property on an INSTANCE.

        Args:
            instance:
            attrname (str):
            value:
        """
        try:
            instance.__dict__[attrname] = value
        except AttributeError:
            # not all objects have __dict__ (e.g. class defines slots)
            msg = (
                f"No '__dict__' attribute on {type(instance).__name__!r} "
                f"instance to cache {attrname!r} property."
            )
            raise TypeError(msg) from None
        except TypeError:
            msg = (
                f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                f"does not support item assignment for caching {attrname!r} property."
            )
            raise TypeError(msg) from None

    @classmethod
    def replace(cls, instance, attrname, value, old_default=None):
        """
        Replace a cached property on an INSTANCE and return the old value.

        Args:
            instance:
            attrname (str):
            value:
            old_default: Default to return if property never cached

        Returns:
            The old cached value, or old_default when the property was not cached
        """
        old = cls.get(instance, attrname, old_default)
        cls.set(instance, attrname, value)
        return old

    @staticmethod
    def warm(instance, attrname):
        """
        Warmup a cached property on an INSTANCE.

        Args:
            instance:
            attrname (str):

        Returns:
            bool: True if warmup or already warmup
                False if failed, or if the property is calculated on await
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

        # an async cached property can't be calculated synchronously
        if getattr(descriptor, 'calculated_on_await', False):
            return False

        # call __get__ function
        try:
            descriptor_get = descriptor.__get__
        except AttributeError:
            return False
        descriptor_get(instance, cls)
        return True


class ClassCacheOperation(CacheOperation):
    """
    Helper functions to manage CLASS cached property.
    """

    @staticmethod
    def pop(cls, attrname, default=None):
        """
        Delete a cached property safely from a CLASS.

        Args:
            cls:
            attrname (str):
            default: Default to return if property never cached
        """
        try:
            # Class mappingproxy is read-only, use type.__delattr__
            # to bypass metaclass __delattr__ and modify the class dict.
            d = cls.__dict__
            if attrname in d:
                val = d[attrname]
                # If it is the descriptor itself, don't delete it
                if isinstance(val, CacheOperation):
                    return default

                # It is a cached value or a normal attribute
                type.__delattr__(cls, attrname)
                # Restore the descriptor if it was backed up by cached_class_property
                desc_name = f"_cached_class_property_desc_for_{attrname}"
                desc = d.get(desc_name, None)
                if desc is not None:
                    type.__setattr__(cls, attrname, desc)
                return val
            return default
        except (AttributeError, TypeError):
            # No __dict__
            return default

    @staticmethod
    def has(cls, attrname):
        """
        Check if a property is cached on a CLASS.

        Args:
            cls:
            attrname (str):
        """
        try:
            d = cls.__dict__
            if attrname not in d:
                return False
            # For class, the descriptor itself IS in __dict__
            # so we check if the value is NOT the descriptor.
            return not isinstance(d[attrname], CacheOperation)
        except AttributeError:
            # No __dict__, just not exists
            return False

    @staticmethod
    def get(cls, attrname, default=None):
        """
        Get a potential cached property from a CLASS without calculating it.

        Args:
            cls:
            attrname (str):
            default: Default to return if property never cached
        """
        try:
            val = cls.__dict__.get(attrname, default)
            if isinstance(val, CacheOperation):
                # It's the descriptor, not the cached value
                return default
            return val
        except AttributeError:
            # No __dict__, just not exists
            return default

    @staticmethod
    def set(cls, attrname, value):
        """
        Set a cached property on a CLASS.

        Args:
            cls:
            attrname (str):
            value:
        """
        try:
            # Class mappingproxy is read-only, use type.__setattr__
            type.__setattr__(cls, attrname, value)
        except (AttributeError, TypeError):
            msg = (
                f"The class {cls.__name__!r} doesn't support "
                f"caching {attrname!r} property."
            )
            raise TypeError(msg) from None

    @classmethod
    def replace(cls, target_cls, attrname, value, old_default=None):
        """
        Replace a cached property on a CLASS and return the old value.

        Args:
            target_cls (type):
            attrname (str):
            value:
            old_default: Default to return if property never cached

        Returns:
            The old cached value, or old_default when the property was not cached
        """
        old = cls.get(target_cls, attrname, old_default)
        cls.set(target_cls, attrname, value)
        return old

    @staticmethod
    def warm(cls, attrname):
        """
        Warmup a cached property on a CLASS.

        Args:
            cls:
            attrname (str):

        Returns:
            bool: True if warmup or already warmup
                False if failed
        """
        try:
            d = cls.__dict__
            if attrname in d:
                # For class, check if it's already a value
                if not isinstance(d[attrname], CacheOperation):
                    return True
        except AttributeError:
            # No '__dict__' attribute
            return False

        # find descriptor
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
        descriptor_get(None, cls)
        return True


class cached_property(Generic[T], InstanceCacheOperation):
    """
    A high-performance, non-thread-safe cached property
    """

    def __init__(self, func: Callable[[Any], T]):
        self.func = func
        wraps(func)(self)

    def __get__(self, instance, cls) -> T:
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

        # calculate
        value = self.func(instance)
        try:
            cache[attrname] = value
        except TypeError:
            msg = (
                f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                f"does not support item assignment for caching {attrname!r} property."
            )
            raise TypeError(msg) from None
        return value


class cached_property_threadsafe(Generic[T], InstanceCacheOperation):
    """
    A thread-safe cached property
    """

    def __init__(self, func: Callable[[Any], T]):
        self.func = func
        # per-property, cross-instance lock, shares among all instances
        self.create_lock = Lock()
        wraps(func)(self)

    @classmethod
    def replace(cls, instance, attrname, value, old_default=None):
        """
        Replace a cached property atomically and return the old value.

        The replacement runs under the same per-instance lock that __get__
        uses, so it can't be lost to a concurrent calculation.

        Args:
            instance:
            attrname (str):
            value:
            old_default: Default to return if property never cached

        Returns:
            The old cached value, or old_default when the property was not cached
        """
        descriptor = getattr(type(instance), attrname, None)
        if not isinstance(descriptor, cls):
            return InstanceCacheOperation.replace(instance, attrname, value, old_default)

        try:
            cache = instance.__dict__
        except AttributeError:
            return InstanceCacheOperation.replace(instance, attrname, value, old_default)

        lock_name = f"_cached_property_lock_for_{attrname}"
        with descriptor.create_lock:
            lock = cache.get(lock_name, None)
            if lock is None:
                lock = Lock()
                try:
                    cache[lock_name] = lock
                except TypeError:
                    return InstanceCacheOperation.replace(instance, attrname, value, old_default)

        with lock:
            old = cache.get(attrname, old_default)
            try:
                cache[attrname] = value
            finally:
                try:
                    del cache[lock_name]
                except KeyError:
                    pass
            return old

    def __get__(self, instance, cls) -> T:
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

        # create pre-instance-property lock
        lock_name = f"_cached_property_lock_for_{attrname}"
        with self.create_lock:
            # double-checked locking
            # check if in cache first to bypass except KeyError for faster because it's not in cache at happy path
            lock = cache.get(lock_name, None)
            if lock is None:
                lock = Lock()
                try:
                    cache[lock_name] = lock
                except TypeError:
                    msg = (
                        f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                        f"does not support item assignment for caching {lock_name!r} property."
                    )
                    raise TypeError(msg) from None

        # calculate value with lock
        with lock:
            # double-checked locking
            # check if the value was computed before the lock was acquired
            # check if in cache first to bypass except KeyError for faster because it's not in cache at happy path
            if attrname in cache:
                try:
                    value = cache[attrname]
                except KeyError:
                    # race condition
                    pass
                else:
                    try:
                        del cache[lock_name]
                    except KeyError:
                        # this shouldn't happen
                        pass
                    return value

            # calculate
            value = self.func(instance)
            try:
                cache[attrname] = value
            except TypeError:
                msg = (
                    f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                    f"does not support item assignment for caching {attrname!r} property."
                )
                raise TypeError(msg) from None

            # cleanup, remove the lock from the instance dict
            # as it will never be used again for this property on this instance
            try:
                del cache[lock_name]
            except KeyError:
                # this shouldn't happen
                pass
            return value


class cached_class_property(Generic[T], ClassCacheOperation):
    """
    A high-performance, non-thread-safe cached class property
    """

    def __init__(self, func: Callable[[type], T]):
        self.func = func
        if isinstance(func, classmethod):
            wraps(func.__func__)(self)
        else:
            wraps(func)(self)

    def __get__(self, instance, cls) -> T:
        """
        Args:
            instance (object): Instance that the property is accessed from,
                can be None if accessed from class.
            cls (type): The class that the property is accessed from.
        """
        attrname = self.__name__
        if isinstance(self.func, classmethod):
            value = self.func.__get__(None, cls)()
        else:
            value = self.func(cls)
        # Back up the descriptor so it can be restored by CacheOperation.pop
        type.__setattr__(cls, f"_cached_class_property_desc_for_{attrname}", self)
        # Use type.__setattr__ to bypass metaclass __setattr__
        # and to work even if cls.__dict__ is mappingproxy
        type.__setattr__(cls, attrname, value)
        return value


class cached_class_property_threadsafe(Generic[T], ClassCacheOperation):
    """
    A thread-safe cached class property
    """

    def __init__(self, func: Callable[[type], T]):
        self.func = func
        # per-property, cross-instance lock, shares among all instances
        self.create_lock = Lock()
        if isinstance(func, classmethod):
            wraps(func.__func__)(self)
        else:
            wraps(func)(self)

    @classmethod
    def replace(cls, target_cls, attrname, value, old_default=None):
        """
        Replace a cached class property atomically and return the old value.

        The replacement runs under the same per-class lock that __get__ uses,
        so it can't be lost to a concurrent calculation.

        Args:
            target_cls (type):
            attrname (str):
            value:
            old_default: Default to return if property never cached

        Returns:
            The old cached value, or old_default when the property was not cached
        """
        descriptor = target_cls.__dict__.get(attrname)
        if not isinstance(descriptor, cls):
            # A cached value replaced the descriptor, the descriptor is kept
            # under a backup key by __get__
            descriptor = target_cls.__dict__.get(f"_cached_class_property_desc_for_{attrname}")
        if not isinstance(descriptor, cls):
            return ClassCacheOperation.replace(target_cls, attrname, value, old_default)

        lock_name = f"_cached_class_property_lock_for_{attrname}"
        with descriptor.create_lock:
            lock = target_cls.__dict__.get(lock_name, None)
            if lock is None:
                lock = Lock()
                try:
                    type.__setattr__(target_cls, lock_name, lock)
                except TypeError:
                    return ClassCacheOperation.replace(target_cls, attrname, value, old_default)

        with lock:
            old = ClassCacheOperation.get(target_cls, attrname, old_default)
            # Preserve the descriptor so pop() can restore it after the replace
            type.__setattr__(target_cls, f"_cached_class_property_desc_for_{attrname}", descriptor)
            try:
                ClassCacheOperation.set(target_cls, attrname, value)
            finally:
                try:
                    type.__delattr__(target_cls, lock_name)
                except AttributeError:
                    pass
            return old

    def __get__(self, instance, cls) -> T:
        """
        Args:
            instance (object): Instance that the property is accessed from,
                can be None if accessed from class.
            cls (type): The class that the property is accessed from.
        """
        attrname = self.__name__
        lock_name = f"_cached_class_property_lock_for_{attrname}"

        with self.create_lock:
            # Use cls.__dict__ to bypass descriptors and __getattr__
            lock = cls.__dict__.get(lock_name, None)
            if lock is None:
                lock = Lock()
                try:
                    type.__setattr__(cls, lock_name, lock)
                except TypeError:
                    msg = (
                        f"The class {cls.__name__!r} doesn't support "
                        f"caching {lock_name!r} property."
                    )
                    raise TypeError(msg) from None

        # calculate value with lock
        with lock:
            # double-checked locking
            # check if in cache first to bypass except KeyError for faster because it's not in cache at happy path
            if attrname in cls.__dict__:
                value = cls.__dict__[attrname]
                # If value is not self, it means it was already calculated by another thread
                if value is not self:
                    try:
                        type.__delattr__(cls, lock_name)
                    except AttributeError:
                        pass
                    return value

            # calculate
            if isinstance(self.func, classmethod):
                value = self.func.__get__(None, cls)()
            else:
                value = self.func(cls)
            try:
                # Back up the descriptor so it can be restored by CacheOperation.pop
                type.__setattr__(cls, f"_cached_class_property_desc_for_{attrname}", self)
                type.__setattr__(cls, attrname, value)
            except TypeError:
                msg = (
                    f"The class {cls.__name__!r} doesn't support "
                    f"caching {attrname!r} property."
                )
                raise TypeError(msg) from None

            # cleanup, remove the lock from the instance dict
            # as it will never be used again for this property on this instance
            try:
                type.__delattr__(cls, lock_name)
            except AttributeError:
                # this shouldn't happen
                pass
            return value
