import gc
from unittest.mock import MagicMock

import pytest
import trio

from oas.backend.reactive.rx_trio import AsyncReactiveCallback, async_reactive, async_reactive_source
from oas.ext.singleton import Singleton

# ---- Test Helper Classes (Now as Singletons) ----


class Calculator(AsyncReactiveCallback, metaclass=Singleton):
    """
    A helper class for testing basic reactive functionalities.
    As a singleton, there will only ever be one instance of Calculator.
    Tests must ensure its state is reset.
    """

    def __init__(self, a=1, b=2):
        # NOTE: __init__ is only called when the singleton is first created.
        self._a = a
        self._b = b
        self.callback_log = []
        # Clear any potential caches from a previous (now-cleared) instance
        self._clear_reactive_caches()

    def _clear_reactive_caches(self):
        # Helper to manually clear caches if needed, though singleton destruction is cleaner.
        for name in ["a", "b", "sum", "product", "complex_expr"]:
            cache_attr = f"_reactive_cache_{name}"
            if hasattr(self, cache_attr):
                delattr(self, cache_attr)

    @async_reactive_source
    async def a(self):
        return self._a

    @async_reactive_source
    async def b(self):
        return self._b

    @async_reactive
    async def sum(self):
        return await self.a + await self.b

    @async_reactive
    async def product(self):
        return await self.a * await self.b

    @async_reactive
    async def complex_expr(self):
        return await self.sum * 10 + await self.product

    async def reactive_callback(self, name, old, new):
        self.callback_log.append((name, old, new))


class DeepDataProcessor(AsyncReactiveCallback, metaclass=Singleton):
    """
    Helper class for testing nested data, now implemented as a singleton.
    """

    def __init__(self):
        self._data = {
            "user": {"profile": {"name": "Alice", "email": "alice@example.com"}},
            "version": 1,
        }
        self.greeting_compute_mock = MagicMock()

    @async_reactive_source
    async def raw_data(self):
        return self._data

    @async_reactive
    async def username(self):
        data = await self.raw_data
        return data["user"]["profile"]["name"]

    @async_reactive
    async def greeting_message(self):
        self.greeting_compute_mock()
        name = await self.username
        return f"Welcome, {name}!"


# ---- Pytest Fixtures ----


@pytest.fixture(autouse=True)
def cleanup_singletons():
    """
    This fixture automatically runs for every test. It cleans up singleton
    instances *after* the test has finished, ensuring each test starts with
    a clean slate. This is crucial for test isolation.
    """
    # Let the test run
    yield
    # After the test, clear all known singleton instances
    Calculator.singleton_clear()
    DeepDataProcessor.singleton_clear()
    # Note: Locally defined singletons inside tests must be cleaned up manually.


@pytest.fixture
def calc():
    """
    Provides the Calculator singleton. Thanks to the `cleanup_singletons`
    fixture, this will be a fresh instance for each test.
    """
    return Calculator(a=3, b=4)


@pytest.fixture
def processor():
    """Provides the DeepDataProcessor singleton, guaranteed to be fresh."""
    return DeepDataProcessor()


# ---- Test Cases ----


@pytest.mark.trio
async def test_initial_computation(calc):
    """Tests if initial values are computed correctly on first access."""
    assert await calc.a == 3
    assert await calc.b == 4
    assert await calc.sum == 7
    assert await calc.product == 12
    assert await calc.complex_expr == (7 * 10 + 12)


@pytest.mark.trio
async def test_dependency_propagation(calc):
    """Tests that changes to a source propagate correctly through the dependency graph."""
    assert await calc.complex_expr == 82
    await calc.a.mutate(5)
    assert await calc.a == 5
    assert await calc.b == 4
    assert await calc.sum == 9
    assert await calc.complex_expr == 110


@pytest.mark.trio
async def test_cross_object_reactivity_with_singletons():
    """
    Tests that a reactive property in one singleton can depend on a property
    in another singleton, and that changes propagate correctly.
    """

    # 1. Setup: Define two singleton classes.
    class SourceProvider(AsyncReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._value = 10

        @async_reactive_source
        async def value(self):
            return self._value

    class DependentConsumer(AsyncReactiveCallback, metaclass=Singleton):
        def __init__(self):
            # Because SourceProvider is a singleton, this will always get
            # the one and only instance.
            self.provider = SourceProvider()
            self.compute_count = 0

        @async_reactive
        async def derived_value(self):
            self.compute_count += 1
            return await self.provider.value * 10

    try:
        # 2. Initial State: Instantiate singletons and check values.
        source = SourceProvider()
        consumer = DependentConsumer()
        assert await source.value == 10
        assert await consumer.derived_value == 100
        assert consumer.compute_count == 1

        # 3. Change Propagation: Modify the source singleton.
        await source.value.mutate(20)

        # The consumer singleton should update automatically.
        assert await consumer.derived_value == 200
        assert consumer.compute_count == 2
    finally:
        # Manually clean up locally defined singletons.
        SourceProvider.singleton_clear()
        DependentConsumer.singleton_clear()


@pytest.mark.trio
async def test_deep_dictionary_dependency(processor):
    """
    Tests dependency tracking on nested data, ensuring updates only happen
    when the relevant slice of data's value changes.
    """
    assert await processor.username == "Alice"
    assert await processor.greeting_message == "Welcome, Alice!"
    processor.greeting_compute_mock.assert_called_once()

    # Irrelevant change
    new_data_irrelevant = (await processor.raw_data).copy()
    new_data_irrelevant["version"] = 2
    await processor.raw_data.mutate()
    assert await processor.username == "Alice"
    assert await processor.greeting_message == "Welcome, Alice!"
    processor.greeting_compute_mock.assert_called_once()  # No new call

    # Relevant change
    new_data_relevant = (await processor.raw_data).copy()
    new_data_relevant["user"]["profile"]["name"] = "Bob"
    await processor.raw_data.mutate()
    assert await processor.username == "Bob"
    assert await processor.greeting_message == "Welcome, Bob!"
    assert processor.greeting_compute_mock.call_count == 2


@pytest.mark.trio
async def test_weakref_observer_cleanup_with_singleton_source():
    """
    Tests that a non-singleton observer is correctly garbage collected even
    when it observes a long-lived singleton.
    """

    # The source is a singleton, representing a long-lived state object.
    class Source(metaclass=Singleton):
        @async_reactive_source
        async def value(self):
            return 0

    # The observer is a regular class, representing an ephemeral UI component, for example.
    class EphemeralObserver:
        def __init__(self, source):
            self.source = source

        @async_reactive
        async def observed_value(self):
            return await self.source.value

    try:
        source_obj = Source()
        observer_obj = EphemeralObserver(source_obj)
        assert await observer_obj.observed_value == 0

        source_value_descriptor = Source.value
        assert len(source_value_descriptor.observers) == 1

        # Delete the only reference to the ephemeral observer.
        del observer_obj
        gc.collect()

        # The observer should be gone from the singleton's observer list.
        assert len(source_value_descriptor.observers) == 0
    finally:
        # Clean up the singleton used in this test.
        Source.singleton_clear()


@pytest.mark.trio
async def test_reactive_callback_invocation():
    """
    Tests that reactive_callback is invoked correctly when reactive properties change.

    Note: In the async version, when using mutate() to set a reactive_source,
    the 'old' parameter is _NOT_FOUND because mutate() is designed for in-place
    mutations where the old value is not available. This is different from the
    sync version where __set__ can capture the old value.
    """
    from oas.backend.reactive.rx_trio import _NOT_FOUND

    class CallbackTracker(AsyncReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._x = 10
            self._y = 20
            self.callback_log = []

        @async_reactive_source
        async def x(self):
            return self._x

        @async_reactive_source
        async def y(self):
            return self._y

        @async_reactive
        async def sum_xy(self):
            return await self.x + await self.y

        async def reactive_callback(self, name, old, new):
            self.callback_log.append((name, old, new))

    try:
        tracker = CallbackTracker()

        # Initial access should not trigger callbacks
        assert await tracker.sum_xy == 30
        # Wait a bit for any potential callbacks to fire
        await trio.testing.wait_all_tasks_blocked()
        assert len(tracker.callback_log) == 0

        # Change x, should trigger callbacks for x and sum_xy
        # Note: old value for x will be _NOT_FOUND due to mutate() behavior
        await tracker.x.mutate(15)
        await trio.testing.wait_all_tasks_blocked()
        assert len(tracker.callback_log) == 2
        # Check x callback - old is _NOT_FOUND in async version
        x_callbacks = [log for log in tracker.callback_log if log[0] == "x"]
        assert len(x_callbacks) == 1
        assert x_callbacks[0] == ("x", _NOT_FOUND, 15)
        # Check sum_xy callback - old value is available for computed properties
        sum_callbacks = [log for log in tracker.callback_log if log[0] == "sum_xy"]
        assert len(sum_callbacks) == 1
        assert sum_callbacks[0] == ("sum_xy", 30, 35)

        # Clear log and change y
        tracker.callback_log.clear()
        await tracker.y.mutate(25)
        await trio.testing.wait_all_tasks_blocked()
        assert len(tracker.callback_log) == 2
        # Check y callback
        y_callbacks = [log for log in tracker.callback_log if log[0] == "y"]
        assert len(y_callbacks) == 1
        assert y_callbacks[0] == ("y", _NOT_FOUND, 25)
        # Check sum_xy callback
        sum_callbacks = [log for log in tracker.callback_log if log[0] == "sum_xy"]
        assert len(sum_callbacks) == 1
        assert sum_callbacks[0] == ("sum_xy", 35, 40)

    finally:
        CallbackTracker.singleton_clear()


@pytest.mark.trio
async def test_parallel_dependencies_no_unnecessary_recompute():
    """
    Tests that in a tree where C depends on both A and B (parallel dependencies),
    when A changes, C recomputes but B does not.

    Dependency graph:
        A   B
         \ /
          C
    """

    class ParallelDeps(AsyncReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._a = 5
            self._b = 10
            self.b_compute_count = 0
            self.c_compute_count = 0

        @async_reactive_source
        async def a(self):
            return self._a

        @async_reactive_source
        async def b(self):
            return self._b

        @async_reactive
        async def b_doubled(self):
            self.b_compute_count += 1
            return await self.b * 2

        @async_reactive
        async def c(self):
            self.c_compute_count += 1
            return await self.a + await self.b_doubled

    try:
        obj = ParallelDeps()

        # Initial computation
        assert await obj.c == 25  # 5 + 10*2 = 25
        assert obj.b_compute_count == 1
        assert obj.c_compute_count == 1

        # Change A, should recompute C but NOT B
        await obj.a.mutate(10)
        assert await obj.c == 30  # 10 + 10*2 = 30
        assert obj.b_compute_count == 1  # B should NOT recompute
        assert obj.c_compute_count == 2  # C should recompute

        # Change B, should recompute both b_doubled and C
        await obj.b.mutate(15)
        assert await obj.c == 40  # 10 + 15*2 = 40
        assert obj.b_compute_count == 2  # B should recompute now
        assert obj.c_compute_count == 3  # C should recompute

    finally:
        ParallelDeps.singleton_clear()


@pytest.mark.trio
async def test_chain_dependencies_no_propagate_if_value_unchanged():
    """
    Tests that in a chain C -> B -> A, when A changes but B's computed value
    remains the same, C does not recompute.

    Dependency graph:
        A -> B -> C

    Note: In async version, reactive_source mutations have _NOT_FOUND as old value.
    """
    from oas.backend.reactive.rx_trio import _NOT_FOUND

    class ChainDeps(AsyncReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._a = 10
            self.b_compute_count = 0
            self.c_compute_count = 0
            self.callback_log = []

        @async_reactive_source
        async def a(self):
            return self._a

        @async_reactive
        async def b(self):
            """B rounds A to nearest 10, so changes in A within same decade don't change B"""
            self.b_compute_count += 1
            a_val = await self.a
            return (a_val // 10) * 10

        @async_reactive
        async def c(self):
            """C depends on B"""
            self.c_compute_count += 1
            return await self.b * 2

        async def reactive_callback(self, name, old, new):
            self.callback_log.append((name, old, new))

    try:
        obj = ChainDeps()

        # Initial computation
        assert await obj.c == 20  # (10//10)*10 * 2 = 10 * 2 = 20
        assert obj.b_compute_count == 1
        assert obj.c_compute_count == 1

        # Change A from 10 to 15, B should recompute but value stays 10, C should NOT recompute
        obj.callback_log.clear()
        await obj.a.mutate(15)
        await trio.testing.wait_all_tasks_blocked()

        assert await obj.b == 10  # (15//10)*10 = 10, unchanged
        assert await obj.c == 20  # Should still be 20
        assert obj.b_compute_count == 2  # B recomputed
        assert obj.c_compute_count == 1  # C should NOT recompute because B value unchanged

        # Check callbacks: only 'a' should have changed, not 'b' or 'c'
        callback_names = [name for name, old, new in obj.callback_log]
        assert "a" in callback_names
        assert "b" not in callback_names  # B didn't change value
        assert "c" not in callback_names  # C didn't change value
        # Verify 'a' callback has _NOT_FOUND as old (due to mutate behavior)
        a_callbacks = [log for log in obj.callback_log if log[0] == "a"]
        assert len(a_callbacks) == 1
        assert a_callbacks[0][1] == _NOT_FOUND  # old value is _NOT_FOUND

        # Now change A to 20, B changes to 20, so C should recompute
        obj.callback_log.clear()
        await obj.a.mutate(20)
        await trio.testing.wait_all_tasks_blocked()

        assert await obj.b == 20  # (20//10)*10 = 20, changed!
        assert await obj.c == 40  # 20 * 2 = 40
        assert obj.b_compute_count == 3  # B recomputed
        assert obj.c_compute_count == 2  # C should recompute now

        # Check callbacks: all three should have changed
        callback_names = [name for name, old, new in obj.callback_log]
        assert "a" in callback_names
        assert "b" in callback_names
        assert "c" in callback_names

    finally:
        ChainDeps.singleton_clear()


@pytest.mark.trio
async def test_complex_tree_selective_recomputation():
    """
    Tests a more complex dependency tree to verify selective recomputation.

    Dependency graph:
        A   B
        |   |
        D   E
         \ /
          F

    When A changes, D and F recompute, but B and E do not.
    """

    class ComplexTree(AsyncReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._a = 1
            self._b = 2
            self.d_compute_count = 0
            self.e_compute_count = 0
            self.f_compute_count = 0

        @async_reactive_source
        async def a(self):
            return self._a

        @async_reactive_source
        async def b(self):
            return self._b

        @async_reactive
        async def d(self):
            self.d_compute_count += 1
            return await self.a * 10

        @async_reactive
        async def e(self):
            self.e_compute_count += 1
            return await self.b * 10

        @async_reactive
        async def f(self):
            self.f_compute_count += 1
            return await self.d + await self.e

    try:
        obj = ComplexTree()

        # Initial computation
        assert await obj.f == 30  # (1*10) + (2*10) = 30
        assert obj.d_compute_count == 1
        assert obj.e_compute_count == 1
        assert obj.f_compute_count == 1

        # Change A, should recompute D and F, but NOT E
        await obj.a.mutate(5)
        assert await obj.f == 70  # (5*10) + (2*10) = 70
        assert obj.d_compute_count == 2  # D recomputed
        assert obj.e_compute_count == 1  # E should NOT recompute
        assert obj.f_compute_count == 2  # F recomputed

        # Change B, should recompute E and F, but NOT D
        await obj.b.mutate(3)
        assert await obj.f == 80  # (5*10) + (3*10) = 80
        assert obj.d_compute_count == 2  # D should NOT recompute
        assert obj.e_compute_count == 2  # E recomputed
        assert obj.f_compute_count == 3  # F recomputed

    finally:
        ComplexTree.singleton_clear()


@pytest.mark.trio
async def test_concurrent_access():
    """
    Tests that concurrent access to reactive properties works correctly.
    """

    class ConcurrentCounter(AsyncReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._value = 0
            self.compute_count = 0

        @async_reactive_source
        async def value(self):
            return self._value

        @async_reactive
        async def doubled(self):
            self.compute_count += 1
            # Simulate some async work
            await trio.sleep(0.01)
            return await self.value * 2

    try:
        counter = ConcurrentCounter()

        # Multiple concurrent accesses should only compute once
        async with trio.open_nursery() as nursery:
            results = []

            async def get_doubled():
                result = await counter.doubled
                results.append(result)

            for _ in range(5):
                nursery.start_soon(get_doubled)

        assert all(r == 0 for r in results)
        assert counter.compute_count == 1  # Should only compute once

    finally:
        ConcurrentCounter.singleton_clear()


@pytest.mark.trio
async def test_cannot_set_reactive_property():
    """
    Tests that attempting to set a reactive property (not reactive_source) raises an error.
    """

    class Sample(AsyncReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._value = 10

        @async_reactive_source
        async def value(self):
            return self._value

        @async_reactive
        async def doubled(self):
            return await self.value * 2

    try:
        obj = Sample()
        assert await obj.doubled == 20

        # Attempting to set a reactive property should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            obj.doubled = 30

        assert "You should not set value to a reactive object" in str(exc_info.value)
        assert "break the observation chain" in str(exc_info.value)

    finally:
        Sample.singleton_clear()


@pytest.mark.trio
async def test_cannot_set_async_reactive_source_synchronously():
    """
    Tests that attempting to set an async_reactive_source synchronously raises TypeError.
    This ensures users are forced to use the async mutate() method.
    """

    class Sample(AsyncReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._value = 10

        @async_reactive_source
        async def value(self):
            return self._value

    try:
        obj = Sample()
        assert await obj.value == 10

        # Attempting to set synchronously should raise TypeError
        with pytest.raises(TypeError) as exc_info:
            obj.value = 20

        error_msg = str(exc_info.value)
        assert "should not set an async reactive source synchronously" in error_msg
        assert "mutate" in error_msg

        # Verify the correct way still works
        await obj.value.mutate(20)
        assert await obj.value == 20

    finally:
        Sample.singleton_clear()
