"""
Tests for ``deep_pop`` in ``oas.ext.deep``.

``deep_pop`` removes and returns a value from a nested dict/list by key path.
It supports popping from a list by index as well as from a dict by key, and
returns ``default`` when the key path does not exist.
"""

from collections import deque

from oas.ext.deep import deep_pop


class TestDeepPop:
    def test_deep_pop_basic(self):
        d = {'a': {'b': 1}}
        assert deep_pop(d, 'a.b') == 1
        assert d == {'a': {}}

    def test_deep_pop_missing(self):
        d = {'a': 1}
        assert deep_pop(d, 'b', default='miss') == 'miss'
        assert d == {'a': 1}

    def test_deep_pop_list(self):
        # Write ops assume dict only: popping from a list returns default
        d = {'a': [1, 2, 3]}
        assert deep_pop(d, ['a', 1], default='miss') == 'miss'
        assert d == {'a': [1, 2, 3]}

    def test_deep_pop_list_root(self):
        # Root is a list, popping is not supported
        d = [0, 1, 2]
        assert deep_pop(d, [1], default='miss') == 'miss'
        assert d == [0, 1, 2]

    def test_deep_pop_nested_list(self):
        d = {'a': [10, 20]}
        assert deep_pop(d, ['a', 0], default='miss') == 'miss'
        assert d == {'a': [10, 20]}

    def test_deep_pop_list_index_error(self):
        # Out-of-range list index is not supported either, returns default
        d = {'a': [1, 2]}
        assert deep_pop(d, ['a', 5], default='miss') == 'miss'
        assert d == {'a': [1, 2]}

    def test_deep_pop_read_path_supports_list(self):
        # Reading path supports list, but the last level must be a dict to pop
        d = {'a': [{'b': 1}]}
        assert deep_pop(d, ['a', 0, 'b'], default='miss') == 1
        assert d == {'a': [{}]}

    def test_deep_pop_empty(self):
        d = {'a': 1}
        assert deep_pop(d, '') is None
        assert deep_pop(d, []) is None  # keys[-1] IndexError caught

    def test_deep_pop_non_dict(self):
        assert deep_pop(1, 'a', default='miss') == 'miss'
        assert deep_pop(None, 'a', default='miss') == 'miss'

    def test_deep_pop_type_error(self):
        # String key on a list -> TypeError (list indices must be integers)
        d = [1, 2]
        assert deep_pop(d, ['a'], default='miss') == 'miss'
        # Non-iterable keys -> TypeError
        assert deep_pop(d, 123, default='miss') == 'miss'

    def test_deep_pop_index_error(self):
        # Out-of-range list index returns default (list is not supported for write)
        d = [1, 2]
        assert deep_pop(d, [5], default='miss') == 'miss'

    def test_deep_pop_middle_not_dict(self):
        # Intermediate value is not a dict -> AttributeError caught
        d = {'a': 1}
        assert deep_pop(d, 'a.b', default='miss') == 'miss'
        assert d == {'a': 1}

    def test_deep_pop_none_value(self):
        # A successful pop of a None value returns None (not default)
        d = {'a': None}
        assert deep_pop(d, 'a', default='miss') is None
        assert d == {}

    def test_deep_pop_returns_reference(self):
        # Pop returns the removed object itself
        inner = {'x': 1}
        d = {'a': inner}
        assert deep_pop(d, 'a') is inner
        assert d == {}

    def test_deep_pop_tuple_keys(self):
        # keys can be a tuple
        d = {'a': {'b': 1}}
        assert deep_pop(d, ('a', 'b')) == 1
        assert d == {'a': {}}

    def test_deep_pop_deque_keys(self):
        # keys can be a deque
        d = {'a': {'b': 1}}
        assert deep_pop(d, deque(['a', 'b'])) == 1
        assert d == {'a': {}}


