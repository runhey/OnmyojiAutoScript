import threading
import time

import pytest

from oas.ext.cache.cache import (
    ClassCacheOperation, cached_class_property, cached_class_property_threadsafe, cached_property,
    cached_property_threadsafe
)


class MockInstance:
    def __init__(self):
        self.count = 0
        self.slow_count = 0

    @cached_property
    def value(self):
        self.count += 1
        return f"value_{self.count}"

    @cached_property_threadsafe
    def slow_value(self):
        time.sleep(0.1)
        self.slow_count += 1
        return f"slow_value_{self.slow_count}"


class MockSlots:
    __slots__ = ("a",)


def test_cached_property():
    obj = MockInstance()

    # First access
    assert obj.value == "value_1"
    assert obj.count == 1

    # Second access (cached)
    assert obj.value == "value_1"
    assert obj.count == 1

    # Check if replaced in __dict__
    assert "value" in obj.__dict__
    assert obj.__dict__["value"] == "value_1"


def test_cache_operation_methods():
    obj = MockInstance()

    # has
    assert cached_property.has(obj, "value") is False
    obj.value
    assert cached_property.has(obj, "value") is True

    # get
    assert cached_property.get(obj, "value") == "value_1"
    assert cached_property.get(obj, "non_existent", "default") == "default"

    # set
    cached_property.set(obj, "value", "manual_value")
    assert obj.value == "manual_value"

    # pop
    val = cached_property.pop(obj, "value")
    assert val == "manual_value"
    assert cached_property.has(obj, "value") is False

    # recalculate after pop
    assert obj.value == "value_2"
    assert obj.count == 2


def test_warmup():
    obj = MockInstance()
    assert cached_property.has(obj, "value") is False

    # Warmup
    success = cached_property.warm(obj, "value")
    assert success is True
    assert cached_property.has(obj, "value") is True
    assert obj.count == 1

    # Already warmup
    success = cached_property.warm(obj, "value")
    assert success is True
    assert obj.count == 1


def test_warmup_inheritance():
    class Parent:
        def __init__(self):
            self.parent_count = 0

        @cached_property
        def parent_val(self):
            self.parent_count += 1
            return "parent"

    class Child(Parent):
        def __init__(self):
            super().__init__()
            self.child_count = 0

        @cached_property
        def child_val(self):
            self.child_count += 1
            return "child"

    obj = Child()
    assert cached_property.has(obj, "parent_val") is False
    assert cached_property.has(obj, "child_val") is False

    # Warmup parent property from child instance
    success = cached_property.warm(obj, "parent_val")
    assert success is True
    assert cached_property.has(obj, "parent_val") is True
    assert obj.parent_val == "parent"
    assert obj.parent_count == 1

    # Warmup child property
    success = cached_property.warm(obj, "child_val")
    assert success is True
    assert cached_property.has(obj, "child_val") is True
    assert obj.child_val == "child"
    assert obj.child_count == 1


def test_threadsafe_cached_property_basic():
    obj = MockInstance()

    # First access
    assert obj.slow_value == "slow_value_1"
    assert obj.slow_count == 1

    # Second access
    assert obj.slow_value == "slow_value_1"
    assert obj.slow_count == 1


def test_threadsafe_cached_property_concurrency():
    obj = MockInstance()
    results = []

    def access_value():
        results.append(obj.slow_value)

    threads = [threading.Thread(target=access_value) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads should get the same value
    assert len(results) == 5
    assert all(r == "slow_value_1" for r in results)
    # The function should be called only once
    assert obj.slow_count == 1


def test_slots_error():
    # cached_property should raise TypeError on objects with __slots__ but no __dict__
    class SlotsWithCached:
        __slots__ = ("_val",)

        @cached_property
        def val(self):
            return 1

    obj = SlotsWithCached()
    with pytest.raises(TypeError, match="No '__dict__' attribute"):
        _ = obj.val


def test_cache_operation_no_dict():
    # An object without __dict__
    obj = 1

    assert cached_property.has(obj, "any") is False
    assert cached_property.get(obj, "any", "def") == "def"
    assert cached_property.pop(obj, "any") is None

    with pytest.raises(TypeError, match="No '__dict__' attribute"):
        cached_property.set(obj, "any", 1)

    assert cached_property.warm(obj, "any") is False


class Meta(type):
    def __getattr__(self, name):
        if name.startswith("__") or name.startswith("_pytest"):
            return super().__getattr__(name)
        raise RuntimeError(f"Meta.__getattr__ called for {name}")

    def __setattr__(self, name, value):
        if name.startswith("__") or name.startswith("_pytest") or name in ["__abstractmethods__", "_abc_impl"]:
             return super().__setattr__(name, value)
        raise RuntimeError(f"Meta.__setattr__ called for {name}")


class MockBase(metaclass=Meta):
    def __init__(self):
        self.attr_calls = 0

    def __getattr__(self, name):
        if name.startswith("__") or name.startswith("_pytest"):
            raise AttributeError(name)
        self.attr_calls += 1
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name == "attr_calls" or name.startswith("__") or name.startswith("_pytest"):
            return super().__setattr__(name, value)
        # We don't want to break everything, but let's track unexpected sets
        raise RuntimeError(f"MockBase.__setattr__ called for {name}")


class MockNoSideEffects(MockBase):
    @cached_property
    def cached_val(self):
        return "ok"

    @cached_property_threadsafe
    def cached_val_ts(self):
        return "ok_ts"


def test_no_side_effects():
    obj = MockNoSideEffects()

    # Check initial state
    assert obj.attr_calls == 0

    # CacheOperation.has should NOT trigger __getattr__
    assert cached_property.has(obj, "cached_val") is False
    assert obj.attr_calls == 0

    # Access cached_val
    # This might trigger __getattribute__ but should NOT trigger __getattr__
    # since it actually finds the descriptor.
    assert obj.cached_val == "ok"
    assert obj.attr_calls == 0

    # Second access (now in __dict__)
    assert obj.cached_val == "ok"
    assert obj.attr_calls == 0

    # CacheOperation.get
    assert cached_property.get(obj, "cached_val") == "ok"
    assert obj.attr_calls == 0

    # CacheOperation.set
    # This should manipulate __dict__ directly, bypassing __setattr__
    cached_property.set(obj, "manual", 123)
    assert obj.manual == 123
    assert obj.attr_calls == 0

    # CacheOperation.pop
    val = cached_property.pop(obj, "manual")
    assert val == 123
    assert obj.attr_calls == 0

    # CacheOperation.warm
    success = cached_property.warm(obj, "cached_val_ts")
    assert success is True
    assert obj.cached_val_ts == "ok_ts"
    assert obj.attr_calls == 0


def test_cached_class_property():
    class TestClass:
        count = 0

        @cached_class_property
        def value(cls):
            cls.count += 1
            return f"val_{cls.count}"

    # First access via class
    assert TestClass.value == "val_1"
    assert TestClass.count == 1
    # Replaced in __dict__
    assert TestClass.__dict__["value"] == "val_1"

    # Second access
    assert TestClass.value == "val_1"
    assert TestClass.count == 1


def test_cached_class_property_threadsafe_concurrency():
    class TestClassTS:
        count = 0

        @cached_class_property_threadsafe
        def value(cls):
            time.sleep(0.1)
            cls.count += 1
            return f"val_{cls.count}"

    results = []

    def access():
        results.append(TestClassTS.value)

    threads = [threading.Thread(target=access) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 5
    assert all(r == "val_1" for r in results)
    assert TestClassTS.count == 1


def test_cached_class_property_no_side_effects():
    # Meta is defined earlier in the file with RuntimeError on __setattr__
    class SideEffectClass(metaclass=Meta):
        @cached_class_property
        def val(cls):
            return "ok"

    # Accessing SideEffectClass.val should use type.__setattr__
    # and bypass Meta.__setattr__ (which raises RuntimeError)
    assert SideEffectClass.val == "ok"
    assert SideEffectClass.__dict__["val"] == "ok"


def test_cache_class_operation_methods():
    class TestClass:
        count = 0

        @cached_class_property
        def value(cls):
            cls.count += 1
            return f"val_{cls.count}"

    cls = TestClass

    # has
    assert cached_class_property.has(cls, "value") is False
    _ = cls.value
    assert cached_class_property.has(cls, "value") is True

    # get
    assert cached_class_property.get(cls, "value") == "val_1"
    assert cached_class_property.get(cls, "non_existent", "default") == "default"

    # set
    cached_class_property.set(cls, "value", "manual_value")
    assert cls.value == "manual_value"

    # pop
    val = cached_class_property.pop(cls, "value")
    assert val == "manual_value"
    assert cached_class_property.has(cls, "value") is False

    # recalculate after pop
    assert cls.value == "val_2"
    assert TestClass.count == 2


def test_class_warmup():
    class TestClassWarm:
        count = 0

        @cached_class_property
        def value(cls):
            cls.count += 1
            return "val"

    cls = TestClassWarm
    assert cached_class_property.has(cls, "value") is False

    # Warmup
    success = cached_class_property.warm(cls, "value")
    assert success is True
    assert cached_class_property.has(cls, "value") is True
    assert cls.count == 1

    # Already warmup
    success = cached_class_property.warm(cls, "value")
    assert success is True
    assert cls.count == 1


def test_class_warmup_inheritance():
    class Parent:
        parent_count = 0

        @cached_class_property
        def parent_val(cls):
            cls.parent_count += 1
            return "parent"

    class Child(Parent):
        child_count = 0

        @cached_class_property
        def child_val(cls):
            cls.child_count += 1
            return "child"

    cls = Child
    assert cached_class_property.has(cls, "parent_val") is False
    assert cached_class_property.has(cls, "child_val") is False

    # Warmup parent property from child class
    success = cached_class_property.warm(cls, "parent_val")
    assert success is True
    assert cached_class_property.has(Child, "parent_val") is True
    assert Child.parent_val == "parent"
    assert Child.parent_count == 1

    # Warmup child property
    success = cached_class_property.warm(cls, "child_val")
    assert success is True
    assert cached_class_property.has(Child, "child_val") is True
    assert Child.child_val == "child"
    assert Child.child_count == 1


def test_class_slots_error():
    # Classes themselves don't usually have __slots__ in simple cases,
    # but some built-in classes or objects might not support it.
    pass


def test_class_cache_operation_no_dict():
    # e.g., int, str
    cls = int

    assert cached_class_property.has(cls, "any") is False
    assert cached_class_property.get(cls, "any", "def") == "def"
    # pop on built-in type should just fail gracefully if no __dict__
    assert cached_class_property.pop(cls, "any") is None

    # set on built-in class should raise TypeError
    with pytest.raises(TypeError):
        cached_class_property.set(cls, "any", 1)

    assert cached_class_property.warm(cls, "any") is False


def test_class_operation_normal_attributes():
    class TestClass:
        a = 1
        b = None

    cls = TestClass
    # has/get
    assert ClassCacheOperation.has(cls, "a") is True
    assert ClassCacheOperation.get(cls, "a") == 1
    assert ClassCacheOperation.has(cls, "b") is True
    assert ClassCacheOperation.get(cls, "b") is None

    # set
    ClassCacheOperation.set(cls, "a", 2)
    assert cls.a == 2

    # pop
    assert ClassCacheOperation.pop(cls, "a") == 2
    assert not hasattr(cls, "a")

    # pop None
    assert ClassCacheOperation.pop(cls, "b") is None
    assert not hasattr(cls, "b")


def test_cached_class_property_via_instance():
    class TestClass:
        count = 0

        @cached_class_property
        def val(cls):
            cls.count += 1
            return f"val_{cls.count}"

    obj = TestClass()
    # Access via instance
    assert obj.val == "val_1"
    assert TestClass.count == 1

    # Check if cached on class
    assert "val" in TestClass.__dict__
    assert TestClass.__dict__["val"] == "val_1"
    # Verify it's NOT in instance dict
    assert "val" not in obj.__dict__

    # Access via class
    assert TestClass.val == "val_1"

    # Access via another instance
    obj2 = TestClass()
    assert obj2.val == "val_1"
    assert TestClass.count == 1


def test_cached_class_property_threadsafe_via_instance():
    class TestClassTS:
        count = 0

        @cached_class_property_threadsafe
        def val(cls):
            time.sleep(0.01)
            cls.count += 1
            return f"val_{cls.count}"

    obj = TestClassTS()
    assert obj.val == "val_1"
    assert TestClassTS.count == 1
    assert "val" in TestClassTS.__dict__
    assert "val" not in obj.__dict__

    # Check another instance
    obj2 = TestClassTS()
    assert obj2.val == "val_1"
    assert TestClassTS.count == 1


def test_cached_class_property_with_classmethod():
    class TestClassCM:
        count = 0

        @cached_class_property
        @classmethod
        def val(cls):
            cls.count += 1
            return f"val_{cls.count}"

    # Via class
    assert TestClassCM.val == "val_1"
    assert TestClassCM.count == 1
    # Check cache
    assert TestClassCM.val == "val_1"
    assert TestClassCM.count == 1

    # Via instance
    obj = TestClassCM()
    assert obj.val == "val_1"
