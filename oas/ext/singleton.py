import threading
from typing import Any, Dict, Optional, Type, TypeVar

T = TypeVar('T')


class Singleton(type):
    """
    A metaclass for creating a global singleton.

    Any class using this metaclass will have only one instance.
    Subclasses will have their own unique singleton instance.
    This implementation is thread-safe.

    Usage:
        class ConfigScanSource(metaclass=Singleton):
            pass
        # first call creates new instance
        source = ConfigScanSource()
        # second and later calls return the same instance
        source = ConfigScanSource()
    """

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        # Per-class singleton storage. Plain (unmangled) names on purpose:
        # the SingletonNamed family shares the storage layout across the
        # metaclass subclasses, name mangling would split it per class.
        cls._singleton_instance = None
        cls._singleton_lock = threading.Lock()

    def __call__(cls: Type[T], *args, **kwargs) -> T:
        # return cached instance directly
        instance = cls._singleton_instance
        if instance is not None:
            return instance

        # create new instance
        with cls._singleton_lock:
            # another thread may have created while we are waiting
            instance = cls._singleton_instance
            if instance is not None:
                return instance

            # create
            instance = super().__call__(*args, **kwargs)
            cls._singleton_instance = instance
            return instance

    def singleton_clear(cls):
        """
        Remove all instances
        """
        with cls._singleton_lock:
            cls._singleton_instance = None

    def singleton_instance(cls) -> Optional[T]:
        """
        Access instance directly
        """
        return cls._singleton_instance

    def singleton_remove_if(cls, instance) -> bool:
        """
        Remove the given instance only when it is the current one.
        Identity-checked removal: a stale remover never deletes a newer
        instance that replaced it at the slot.

        Args:
            instance: The instance to remove

        Returns:
            bool: If removed
        """
        with cls._singleton_lock:
            if cls._singleton_instance is instance:
                cls._singleton_instance = None
                return True
        return False

    def singleton_reinsert(cls, instance) -> bool:
        """
        Restore the given instance when the slot is vacant.
        Called at subscribe time by sources: a concurrent idle GC may have
        removed the instance while a subscription flow was in flight, and a
        live subscriber means the instance is wanted again.

        Args:
            instance: The instance to restore

        Returns:
            bool: If restored (slot was vacant)
        """
        with cls._singleton_lock:
            if cls._singleton_instance is None:
                cls._singleton_instance = instance
                return True
        return False


class SingletonNamed(type):
    """
    A metaclass for creating a named singleton.

    Instances are created based on the first argument provided to the constructor.
    Each class will have its own separate cache of named instances.
    This implementation is thread-safe.

    Usage:
        class AlasioConfigDB(metaclass=SingletonNamed):
            # __init__ must have at least one argument
            def __init__(self, config_name):
                self.file = config_name

        # first call creates new instance
        db = AlasioConfigDB("alas")
        # second and later calls return the same instance
        db = AlasioConfigDB("alas")
        # different input different instance
        db2 = AlasioConfigDB("alas2")
    """

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        # Per-class named-instance storage. Plain (unmangled) names on
        # purpose: the SingletonNamed family (incl. SingletonKeyed) shares
        # the storage layout, name mangling would split it per class.
        cls._singleton_instances = {}
        cls._singleton_lock = threading.Lock()

    def __call__(cls: Type[T], name, *args, **kwargs) -> T:
        # return cached instance directly
        instance = cls._singleton_instances.get(name)
        if instance is not None:
            return instance

        # create new instance
        with cls._singleton_lock:
            # another thread may have created while we are waiting
            # it is rare case so check if key is in first
            if name in cls._singleton_instances:
                try:
                    return cls._singleton_instances[name]
                except KeyError:
                    pass

            # create
            instance = super().__call__(name, *args, **kwargs)
            cls._singleton_instances[name] = instance
            return instance

    def singleton_remove(cls, name):
        """
        Remove a specific instance.
        Instance will be re-created, the nest time it is requested.

        Returns:
            bool: If removed
        """
        # delete from dict is threadsafe
        try:
            del cls._singleton_instances[name]
            return True
        except KeyError:
            return False

    def singleton_remove_if(cls, name, instance) -> bool:
        """
        Remove the instance at name only when it is the given instance.
        Identity-checked removal: a stale remover never deletes a newer
        instance that replaced it at the slot.

        Args:
            name: Instance name (key)
            instance: The instance to remove

        Returns:
            bool: If removed
        """
        with cls._singleton_lock:
            if cls._singleton_instances.get(name) is instance:
                del cls._singleton_instances[name]
                return True
        return False

    def singleton_reinsert(cls, name, instance) -> bool:
        """
        Restore the instance at name when the slot is vacant.
        Called at subscribe time by sources: a concurrent idle GC may have
        removed the instance while a subscription flow was in flight, and a
        live subscriber means the instance is wanted again.

        Args:
            name (str): Instance name (key)
            instance: The instance to restore

        Returns:
            bool: If restored (slot was vacant)
        """
        with cls._singleton_lock:
            if name not in cls._singleton_instances:
                cls._singleton_instances[name] = instance
                return True
        return False

    def singleton_items(cls):
        """
        Snapshot the (name, instance) pairs under the lock.
        Thread-safe enumeration for GC / dispatch loops that must never
        mutate the dict while iterating it.

        Returns:
            list[tuple]: List of (name, instance)
        """
        with cls._singleton_lock:
            return list(cls._singleton_instances.items())

    def singleton_clear(cls):
        """
        Remove all instances
        """
        with cls._singleton_lock:
            cls._singleton_instances.clear()

    def singleton_instances(cls) -> Dict[Any, T]:
        """
        Access all instances directly
        """
        return cls._singleton_instances


class SingletonOptionalNamed(SingletonNamed):
    """
    A metaclass combining global singleton and named singleton behavior.

    When a name is provided, it acts as a named singleton (like SingletonNamed).
    When no name is provided (or None), it acts as a global singleton (like Singleton).
    The unnamed instance shares the same cache, stored under the key None.
    This implementation is thread-safe.

    Usage:
        class MyService(metaclass=SingletonOptionalNamed):
            def __init__(self, name=None, value=0):
                self.name = name
                self.value = value

        # unnamed: global singleton
        s1 = MyService()
        s2 = MyService()
        assert s1 is s2

        # named: named singleton
        s3 = MyService("a")
        s4 = MyService("a")
        assert s3 is s4
        s5 = MyService("b")
        assert s3 is not s5
    """

    def __call__(cls, name=None, *args, **kwargs):
        """
        Return a singleton instance.

        Args:
            name: Optional name for named singleton behavior.
                When None, behaves as a global singleton.

        Returns:
            The singleton instance.
        """
        return super().__call__(name, *args, **kwargs)


class SingletonKeyed(SingletonNamed):
    """
    A metaclass for creating a keyed singleton where the WHOLE positional
    argument tuple of the constructor is the key.

    SingletonNamed keys on the first constructor argument only; this
    variant takes every positional argument as part of the composite key,
    while the constructor still receives them unpacked -- subclasses keep
    natural signatures such as `__init__(self, mod_name, lang)`.

    This implementation is thread-safe. The created instance stores its
    key as `_singleton_key` (set by the metaclass), so registries can
    remove it by identity.

    Usage:
        class ConfigNavSource(metaclass=SingletonKeyed):
            def __init__(self, mod_name, lang):
                pass

        # every positional argument forms the composite key
        a = ConfigNavSource('alas', 'zh-CN')
        b = ConfigNavSource('alas', 'zh-CN')  # a is b
        c = ConfigNavSource('alas', 'en-US')  # different key, new instance
    """

    def __call__(cls: Type[T], *key) -> T:
        # return cached instance directly
        instance = cls._singleton_instances.get(key)
        if instance is not None:
            return instance

        # create new instance
        with cls._singleton_lock:
            # another thread may have created while we are waiting
            # it is rare case so check if key is in first
            if key in cls._singleton_instances:
                try:
                    return cls._singleton_instances[key]
                except KeyError:
                    pass

            # create with the key unpacked: subclasses keep natural
            # __init__(mod, lang, ...) signatures
            instance = type.__call__(cls, *key)
            instance._singleton_key = key
            cls._singleton_instances[key] = instance
            return instance
