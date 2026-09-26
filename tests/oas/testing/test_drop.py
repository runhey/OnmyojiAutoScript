import pytest

from oas.testing.drop import function_drop


class TestFunctionDrop:
    """Tests for function_drop decorator on plain functions."""

    def test_drop_rate_zero(self):
        """With drop_rate=0 the function is always called."""
        calls = []

        @function_drop(0.0, default=None, log=False)
        def target(x):
            calls.append(x)
            return x * 2

        result = target(5)
        assert result == 10
        assert calls == [5]

    def test_drop_rate_one(self):
        """With drop_rate=1 the function is always dropped."""
        calls = []

        @function_drop(1.0, default=42, log=False)
        def target(x):
            calls.append(x)
            return x * 2

        result = target(7)
        assert result == 42
        assert calls == []

    def test_default_ellipsis(self):
        """Default value is Ellipsis when not specified."""
        @function_drop(1.0, log=False)
        def target():
            return "called"

        result = target()
        assert result is Ellipsis

    def test_custom_default(self):
        """Custom default is returned when the call is dropped."""
        @function_drop(1.0, default="fallback", log=False)
        def target():
            return "called"

        result = target()
        assert result == "fallback"

    def test_kwargs_preserved(self):
        """Keyword arguments are forwarded correctly when not dropped."""
        @function_drop(0.0, log=False)
        def target(a, b=10):
            return a + b

        assert target(1, b=2) == 3
        assert target(5) == 15

    def test_wraps_preserved(self):
        """functools.wraps preserves function name and docstring."""
        @function_drop(0.5, log=False)
        def my_func():
            """My docstring."""
            return 0

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."

    def test_log_output(self, capsys):
        """When log=True a message is printed on drop with full qualname."""
        @function_drop(1.0, default=0, log=True)
        def target(a, b=2):
            return a + b

        target(10, b=20)

        # Full __qualname__ includes the test class and <locals>
        expected = f'Dropped: {target.__qualname__}(10, b=20)'
        assert expected in capsys.readouterr().out

    def test_log_false(self, capsys):
        """When log=False no message is printed on drop."""
        @function_drop(1.0, default=0, log=False)
        def target():
            pass

        target()

        assert capsys.readouterr().out == ''

    def test_no_args(self):
        """Function with no arguments works correctly."""
        @function_drop(0.0, log=False)
        def target():
            return 42

        assert target() == 42

    def test_multiple_calls(self):
        """Multiple calls with drop_rate=0 all go through."""
        results = []

        @function_drop(0.0, log=False)
        def target(x):
            results.append(x)
            return x * 2

        for i in range(5):
            assert target(i) == i * 2

        assert results == [0, 1, 2, 3, 4]

    @pytest.mark.parametrize("drop_rate, expected_calls", [
        (0.0, True),
        (1.0, False),
    ])
    def test_deterministic_rates(self, drop_rate, expected_calls):
        """Deterministic drop_rate values produce correct behavior."""
        calls = []

        @function_drop(drop_rate, default="dropped", log=False)
        def target():
            calls.append(1)
            return "called"

        result = target()

        if expected_calls:
            assert result == "called"
            assert len(calls) == 1
        else:
            assert result == "dropped"
            assert len(calls) == 0


class TestFunctionDropMethod:
    """Tests for function_drop when decorating methods."""

    def test_method_log_excludes_self(self, capsys):
        """Print message for an instance method excludes self and includes class name."""
        class MyClass:
            @function_drop(1.0, default=0, log=True)
            def my_method(self, a, b=10):
                return a + b

        obj = MyClass()
        obj.my_method(1, b=2)

        # Full __qualname__ includes <locals> nesting; self is excluded from the print
        expected = f'Dropped: {MyClass.my_method.__qualname__}(1, b=2)'
        assert expected in capsys.readouterr().out

    def test_method_log_no_args(self, capsys):
        """Print message for a method with only self excludes self."""
        class MyClass:
            @function_drop(1.0, default=0, log=True)
            def my_method(self):
                return 42

        obj = MyClass()
        obj.my_method()

        expected = f'Dropped: {MyClass.my_method.__qualname__}()'
        assert expected in capsys.readouterr().out

    def test_method_not_dropped(self):
        """Method with drop_rate=0 calls the real method correctly."""
        class MyClass:
            @function_drop(0.0, default=0, log=False)
            def my_method(self, x):
                return x * 2

        obj = MyClass()
        assert obj.my_method(5) == 10

    def test_method_dropped_default(self):
        """Method with drop_rate=1 returns the default value."""
        class MyClass:
            @function_drop(1.0, default=-1, log=False)
            def my_method(self, x):
                return x * 2

        obj = MyClass()
        assert obj.my_method(5) == -1

    def test_classmethod_log_excludes_cls(self, capsys):
        """Print message for a classmethod excludes cls and includes class name."""
        class MyClass:
            @classmethod
            @function_drop(1.0, default=0, log=True)
            def my_classmethod(cls, a, b=10):
                return a + b

        MyClass.my_classmethod(1, b=2)

        # cls is excluded from the print, the class name is in __qualname__
        expected = f'Dropped: {MyClass.my_classmethod.__qualname__}(1, b=2)'
        assert expected in capsys.readouterr().out

    def test_staticmethod_log(self, capsys):
        """Print message for a staticmethod uses __qualname__ (includes class prefix)."""
        class MyClass:
            @staticmethod
            @function_drop(1.0, default=0, log=True)
            def my_staticmethod(a, b=10):
                return a + b

        MyClass.my_staticmethod(1, b=2)

        # No self/cls to exclude, __qualname__ still carries the class prefix
        expected = f'Dropped: {MyClass.my_staticmethod.__qualname__}(1, b=2)'
        assert expected in capsys.readouterr().out
