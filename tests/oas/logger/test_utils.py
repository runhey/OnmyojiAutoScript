from oas.logger.utils import event_args_format, event_format, join_event_dict, stringify_event


class TestStringifyEvent:
    def test_stringify_event_str(self):
        assert stringify_event("hello") == "hello"
        assert stringify_event("") == ""

    def test_stringify_event_exception_instance(self):
        # Exception with message
        exc = ValueError("invalid value")
        assert stringify_event(exc) == "ValueError: invalid value"

        # Exception without message
        exc = ValueError()
        assert stringify_event(exc) == "ValueError"

    def test_stringify_event_exception_class(self):
        assert stringify_event(ValueError) == "ValueError"
        assert stringify_event(RuntimeError) == "RuntimeError"

    def test_stringify_event_exception_group(self):
        e1 = ValueError("e1")
        e2 = TypeError("e2")
        eg = ExceptionGroup("group", [e1, e2])

        result = stringify_event(eg)
        # ExceptionGroup: group
        # - ValueError: e1
        # - TypeError: e2
        assert result.startswith("ExceptionGroup: group")
        assert "- ValueError: e1" in result
        assert "- TypeError: e2" in result

    def test_stringify_event_nested_exception_group(self):
        e1 = ValueError("e1")
        e2 = TypeError("e2")
        eg_inner = ExceptionGroup("inner", [e2])
        eg_outer = ExceptionGroup("outer", [e1, eg_inner])

        result = stringify_event(eg_outer)
        # ExceptionGroup: outer
        # - ValueError: e1
        # - ExceptionGroup: inner
        #   - TypeError: e2
        assert result.startswith("ExceptionGroup: outer")
        assert "- ValueError: e1" in result
        assert "- ExceptionGroup: inner" in result
        assert "  - TypeError: e2" in result

    def test_stringify_event_other_types(self):
        assert stringify_event(123) == "123"
        assert stringify_event([1, 2]) == "[1, 2]"
        assert stringify_event(None) == "None"


class TestEventFormat:
    def test_event_format_basic(self):
        assert event_format("Hello {name}", {"name": "World"}) == "Hello World"

    def test_event_format_missing_key(self):
        # Should use SafeDict and return placeholder
        assert event_format("Hello {name} {age}", {"name": "Alice"}) == 'Hello Alice <key "age" missing>'

    def test_event_format_no_braces(self):
        assert event_format("Hello World", {"name": "Alice"}) == "Hello World"

    def test_event_format_empty_dict(self):
        assert event_format("Hello {name}", {}) == "Hello {name}"

    def test_event_format_mixed_keys(self):
        # 'name' is a user key, so it should format
        assert event_format("Hello {name}", {"name": "Bob", "exception": ValueError()}) == "Hello Bob"

    def test_event_format_unpaired_braces(self):
        # Formatting should fail silently and return original string
        assert event_format("Hello {name", {"name": "Bob"}) == "Hello {name"

    def test_event_format_complex_formatting(self):
        # Test with multiple keys and types
        event = "{user} logged in from {ip} at {time}"
        event_dict = {"user": "admin", "ip": "127.0.0.1", "time": 123456}
        assert event_format(event, event_dict) == "admin logged in from 127.0.0.1 at 123456"

    def test_event_format_with_set_and_dict_literals(self):
        # Case where event contains f-string style set/dict literals
        # and event_dict has user keys (e.g. from bind)
        event = "Set: {'a', 'b'}, Dict: {'k': 'v'}"
        event_dict = {"user": "admin"}

        # These {} should NOT be treated as variables.
        # Dict literal containing colon will raise ValueError in format() and be returned as-is.
        # Set literal will raise KeyError, but SafeDict will preserve it because "'a', 'b'" is not an identifier.
        assert event_format(event, event_dict) == event

    def test_event_format_mixed_variable_and_set_literal(self):
        # Mixed case: one real variable, one set literal
        modules = {'combat_ui', }
        event = "User {user} has set " + str(modules)
        event_dict = {"user": "admin"}

        # {user} should be formatted, {'a'} should be preserved.
        assert event_format(event, event_dict) == "User admin has set {'combat_ui'}"


class TestEventArgsFormat:
    def test_event_args_format_single(self):
        assert event_args_format("Hello %s", "World") == "Hello World"

    def test_event_args_format_tuple(self):
        assert event_args_format("Hello %s %s", ("World", "!")) == "Hello World !"

    def test_event_args_format_dict(self):
        assert event_args_format("Hello %(name)s", {"name": "World"}) == "Hello World"

    def test_event_args_format_error(self):
        # Should fail silently and return original string
        assert event_args_format("Hello %s", ()) == "Hello %s"

    def test_event_args_format_no_percent(self):
        assert event_args_format("Hello World", "Something") == "Hello World"

    def test_event_args_format_empty_args(self):
        assert event_args_format("Hello %s", None) == "Hello %s"
        assert event_args_format("Hello %s", ()) == "Hello %s"


class TestJoinEventDict:
    def test_join_event_dict_basic(self):
        assert join_event_dict("Hello", {"user": "May"}) == "Hello, user='May'"

    def test_join_event_dict_multiple(self):
        # Order is preserved in modern Python dicts
        assert join_event_dict("Hello", {"user": "May", "age": 18}) == "Hello, user='May', age=18"

    def test_join_event_dict_empty_event(self):
        assert join_event_dict("", {"user": "May"}) == "user='May'"

    def test_join_event_dict_empty_dict(self):
        assert join_event_dict("Hello", {}) == "Hello"

    def test_join_event_dict_none_dict(self):
        assert join_event_dict("Hello", None) == "Hello"

    def test_join_event_dict_complex_types(self):
        assert join_event_dict("Log", {"data": [1, 2], "val": None}) == "Log, data=[1, 2], val=None"
