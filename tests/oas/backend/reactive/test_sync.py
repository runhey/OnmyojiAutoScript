import gc
from unittest.mock import MagicMock

import pytest

from oas.backend.reactive.rx_sync import ReactiveCallback, reactive, reactive_source
from oas.ext.singleton import Singleton

# ---- Test Helper Classes (Now as Singletons) ----


class Calculator(ReactiveCallback, metaclass=Singleton):
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
        for name in ['a', 'b', 'sum', 'product', 'complex_expr']:
            cache_attr = f'_reactive_cache_{name}'
            if hasattr(self, cache_attr):
                delattr(self, cache_attr)

    @reactive_source
    def a(self):
        return self._a

    @reactive_source
    def b(self):
        return self._b

    @reactive
    def sum(self):
        return self.a + self.b

    @reactive
    def product(self):
        return self.a * self.b

    @reactive
    def complex_expr(self):
        return self.sum * 10 + self.product

    def reactive_callback(self, name, old, new):
        self.callback_log.append((name, old, new))


class DeepDataProcessor(ReactiveCallback, metaclass=Singleton):
    """
    Helper class for testing nested data, now implemented as a singleton.
    """

    def __init__(self):
        self._data = {
            'user': {'profile': {'name': 'Alice', 'email': 'alice@example.com'}},
            'version': 1
        }
        self.greeting_compute_mock = MagicMock()

    @reactive_source
    def raw_data(self):
        return self._data

    @reactive
    def username(self):
        return self.raw_data['user']['profile']['name']

    @reactive
    def greeting_message(self):
        self.greeting_compute_mock()
        return f"Welcome, {self.username}!"


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

def test_initial_computation(calc):
    """Tests if initial values are computed correctly on first access."""
    assert calc.a == 3
    assert calc.b == 4
    assert calc.sum == 7
    assert calc.product == 12
    assert calc.complex_expr == (7 * 10 + 12)


def test_dependency_propagation(calc):
    """Tests that changes to a source propagate correctly through the dependency graph."""
    assert calc.complex_expr == 82
    calc.a = 5
    assert calc.a == 5
    assert calc.b == 4
    assert calc.sum == 9
    assert calc.complex_expr == 110


def test_cross_object_reactivity_with_singletons():
    """
    Tests that a reactive property in one singleton can depend on a property
    in another singleton, and that changes propagate correctly.
    """

    # 1. Setup: Define two singleton classes.
    class SourceProvider(ReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._value = 10

        @reactive_source
        def value(self):
            return self._value

    class DependentConsumer(ReactiveCallback, metaclass=Singleton):
        def __init__(self):
            # Because SourceProvider is a singleton, this will always get
            # the one and only instance.
            self.provider = SourceProvider()
            self.compute_count = 0

        @reactive
        def derived_value(self):
            self.compute_count += 1
            return self.provider.value * 10

    try:
        # 2. Initial State: Instantiate singletons and check values.
        source = SourceProvider()
        consumer = DependentConsumer()
        assert source.value == 10
        assert consumer.derived_value == 100
        assert consumer.compute_count == 1

        # 3. Change Propagation: Modify the source singleton.
        source.value = 20

        # The consumer singleton should update automatically.
        assert consumer.derived_value == 200
        assert consumer.compute_count == 2
    finally:
        # Manually clean up locally defined singletons.
        SourceProvider.singleton_clear()
        DependentConsumer.singleton_clear()


def test_deep_dictionary_dependency(processor):
    """
    Tests dependency tracking on nested data, ensuring updates only happen
    when the relevant slice of data's value changes.
    """
    assert processor.username == 'Alice'
    assert processor.greeting_message == 'Welcome, Alice!'
    processor.greeting_compute_mock.assert_called_once()

    # Irrelevant change
    new_data_irrelevant = processor.raw_data.copy()
    new_data_irrelevant['version'] = 2
    processor.raw_data = new_data_irrelevant
    assert processor.username == 'Alice'
    assert processor.greeting_message == 'Welcome, Alice!'
    processor.greeting_compute_mock.assert_called_once()  # No new call

    # Relevant change
    new_data_relevant = processor.raw_data.copy()
    new_data_relevant['user']['profile']['name'] = 'Bob'
    DeepDataProcessor.raw_data.mutate(processor)
    assert processor.username == 'Bob'
    assert processor.greeting_message == 'Welcome, Bob!'
    assert processor.greeting_compute_mock.call_count == 2


def test_weakref_observer_cleanup_with_singleton_source():
    """
    Tests that a non-singleton observer is correctly garbage collected even
    when it observes a long-lived singleton.
    """

    # The source is a singleton, representing a long-lived state object.
    class Source(metaclass=Singleton):
        @reactive_source
        def value(self): return 0

    # The observer is a regular class, representing an ephemeral UI component, for example.
    class EphemeralObserver:
        def __init__(self, source): self.source = source

        @reactive
        def observed_value(self): return self.source.value

    try:
        source_obj = Source()
        observer_obj = EphemeralObserver(source_obj)
        assert observer_obj.observed_value == 0

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


def test_reactive_callback_invocation():
    """
    Tests that reactive_callback is invoked correctly when reactive properties change.
    """

    class CallbackTracker(ReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._x = 10
            self._y = 20
            self.callback_log = []

        @reactive_source
        def x(self):
            return self._x

        @reactive_source
        def y(self):
            return self._y

        @reactive
        def sum_xy(self):
            return self.x + self.y

        def reactive_callback(self, name, old, new):
            self.callback_log.append((name, old, new))

    try:
        tracker = CallbackTracker()

        # Initial access should not trigger callbacks
        assert tracker.sum_xy == 30
        assert len(tracker.callback_log) == 0

        # Change x, should trigger callbacks for x and sum_xy
        tracker.x = 15
        assert len(tracker.callback_log) == 2
        assert ('x', 10, 15) in tracker.callback_log
        assert ('sum_xy', 30, 35) in tracker.callback_log

        # Clear log and change y
        tracker.callback_log.clear()
        tracker.y = 25
        assert len(tracker.callback_log) == 2
        assert ('y', 20, 25) in tracker.callback_log
        assert ('sum_xy', 35, 40) in tracker.callback_log

    finally:
        CallbackTracker.singleton_clear()


def test_parallel_dependencies_no_unnecessary_recompute():
    """
    Tests that in a tree where C depends on both A and B (parallel dependencies),
    when A changes, C recomputes but B does not.

    Dependency graph:
        A   B
         \ /
          C
    """

    class ParallelDeps(ReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._a = 5
            self._b = 10
            self.b_compute_count = 0
            self.c_compute_count = 0

        @reactive_source
        def a(self):
            return self._a

        @reactive_source
        def b(self):
            return self._b

        @reactive
        def b_doubled(self):
            self.b_compute_count += 1
            return self.b * 2

        @reactive
        def c(self):
            self.c_compute_count += 1
            return self.a + self.b_doubled

    try:
        obj = ParallelDeps()

        # Initial computation
        assert obj.c == 25  # 5 + 10*2 = 25
        assert obj.b_compute_count == 1
        assert obj.c_compute_count == 1

        # Change A, should recompute C but NOT B
        obj.a = 10
        assert obj.c == 30  # 10 + 10*2 = 30
        assert obj.b_compute_count == 1  # B should NOT recompute
        assert obj.c_compute_count == 2  # C should recompute

        # Change B, should recompute both b_doubled and C
        obj.b = 15
        assert obj.c == 40  # 10 + 15*2 = 40
        assert obj.b_compute_count == 2  # B should recompute now
        assert obj.c_compute_count == 3  # C should recompute

    finally:
        ParallelDeps.singleton_clear()


def test_chain_dependencies_no_propagate_if_value_unchanged():
    """
    Tests that in a chain C -> B -> A, when A changes but B's computed value
    remains the same, C does not recompute.

    Dependency graph:
        A -> B -> C
    """

    class ChainDeps(ReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._a = 10
            self.b_compute_count = 0
            self.c_compute_count = 0
            self.callback_log = []

        @reactive_source
        def a(self):
            return self._a

        @reactive
        def b(self):
            """B rounds A to nearest 10, so changes in A within same decade don't change B"""
            self.b_compute_count += 1
            return (self.a // 10) * 10

        @reactive
        def c(self):
            """C depends on B"""
            self.c_compute_count += 1
            return self.b * 2

        def reactive_callback(self, name, old, new):
            self.callback_log.append((name, old, new))

    try:
        obj = ChainDeps()

        # Initial computation
        assert obj.c == 20  # (10//10)*10 * 2 = 10 * 2 = 20
        assert obj.b_compute_count == 1
        assert obj.c_compute_count == 1

        # Change A from 10 to 15, B should recompute but value stays 10, C should NOT recompute
        obj.callback_log.clear()
        obj.a = 15

        assert obj.b == 10  # (15//10)*10 = 10, unchanged
        assert obj.c == 20  # Should still be 20
        assert obj.b_compute_count == 2  # B recomputed
        assert obj.c_compute_count == 1  # C should NOT recompute because B value unchanged

        # Check callbacks: only 'a' should have changed, not 'b' or 'c'
        callback_names = [name for name, old, new in obj.callback_log]
        assert 'a' in callback_names
        assert 'b' not in callback_names  # B didn't change value
        assert 'c' not in callback_names  # C didn't change value

        # Now change A to 20, B changes to 20, so C should recompute
        obj.callback_log.clear()
        obj.a = 20

        assert obj.b == 20  # (20//10)*10 = 20, changed!
        assert obj.c == 40  # 20 * 2 = 40
        assert obj.b_compute_count == 3  # B recomputed
        assert obj.c_compute_count == 2  # C should recompute now

        # Check callbacks: all three should have changed
        callback_names = [name for name, old, new in obj.callback_log]
        assert 'a' in callback_names
        assert 'b' in callback_names
        assert 'c' in callback_names

    finally:
        ChainDeps.singleton_clear()


def test_complex_tree_selective_recomputation():
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

    class ComplexTree(ReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._a = 1
            self._b = 2
            self.d_compute_count = 0
            self.e_compute_count = 0
            self.f_compute_count = 0

        @reactive_source
        def a(self):
            return self._a

        @reactive_source
        def b(self):
            return self._b

        @reactive
        def d(self):
            self.d_compute_count += 1
            return self.a * 10

        @reactive
        def e(self):
            self.e_compute_count += 1
            return self.b * 10

        @reactive
        def f(self):
            self.f_compute_count += 1
            return self.d + self.e

    try:
        obj = ComplexTree()

        # Initial computation
        assert obj.f == 30  # (1*10) + (2*10) = 30
        assert obj.d_compute_count == 1
        assert obj.e_compute_count == 1
        assert obj.f_compute_count == 1

        # Change A, should recompute D and F, but NOT E
        obj.a = 5
        assert obj.f == 70  # (5*10) + (2*10) = 70
        assert obj.d_compute_count == 2  # D recomputed
        assert obj.e_compute_count == 1  # E should NOT recompute
        assert obj.f_compute_count == 2  # F recomputed

        # Change B, should recompute E and F, but NOT D
        obj.b = 3
        assert obj.f == 80  # (5*10) + (3*10) = 80
        assert obj.d_compute_count == 2  # D should NOT recompute
        assert obj.e_compute_count == 2  # E recomputed
        assert obj.f_compute_count == 3  # F recomputed

    finally:
        ComplexTree.singleton_clear()


def test_cannot_set_reactive_property():
    """
    Tests that attempting to set a reactive property (not reactive_source) raises an error.
    """

    class Sample(ReactiveCallback, metaclass=Singleton):
        def __init__(self):
            self._value = 10

        @reactive_source
        def value(self):
            return self._value

        @reactive
        def doubled(self):
            return self.value * 2

    try:
        obj = Sample()
        assert obj.doubled == 20

        # Attempting to set a reactive property should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            obj.doubled = 30

        assert "You should not set value to a reactive object" in str(exc_info.value)
        assert "break the observation chain" in str(exc_info.value)

    finally:
        Sample.singleton_clear()
