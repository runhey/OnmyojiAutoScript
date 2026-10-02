"""
Tests for the read functions in ``oas.ext.deep``:

- ``deep_get``: get a value from nested dict/list, return default on failure
- ``deep_get_with_error``: get a value, raise KeyError on failure
- ``deep_exist``: check whether a key path exists

Key paths are accepted either as a str like ``"a.b.c"`` (split on ``.``) or as
a list like ``["a", "b", "c"]``.  Lists in the container may be indexed by
integer keys.
"""

from collections import deque

import pytest

from oas.ext.deep import deep_exist, deep_get, deep_get_with_error


class TestDeepGet:
    def test_deep_get_basic(self):
        d = {'a': {'b': {'c': 1}}}
        assert deep_get(d, 'a.b.c') == 1
        assert deep_get(d, ['a', 'b', 'c']) == 1

    def test_deep_get_default(self):
        d = {'a': {'b': {'c': 1}}}
        assert deep_get(d, 'a.b.d', default=2) == 2
        assert deep_get(d, 'a.x.c', default=None) is None

    def test_deep_get_list(self):
        d = {'a': [{'b': 1}, {'b': 2}]}
        assert deep_get(d, ['a', 0, 'b']) == 1
        assert deep_get(d, ['a', 1, 'b']) == 2
        # Index error
        assert deep_get(d, ['a', 2, 'b'], default='err') == 'err'

    def test_deep_get_list_input(self):
        # Support list as input d
        d = [10, 20, 30]
        assert deep_get(d, [1]) == 20
        assert deep_get(d, [5], default=None) is None

    def test_deep_get_mixed_dict_list(self):
        d = [0, [10, 11], 2]
        assert deep_get(d, [1, 0]) == 10
        assert deep_get(d, [1, 1]) == 11
        assert deep_get(d, [2]) == 2

    def test_deep_get_empty_keys(self):
        d = {'a': 1}
        assert deep_get(d, []) == d
        # ''.split('.') is [''], d[''] raises KeyError, returns default
        assert deep_get(d, '') is None
        assert deep_get(d, '.') is None

    def test_deep_get_unicode(self):
        d = {'浣犲ソ': {'涓栫晫': 123}}
        assert deep_get(d, '浣犲ソ.涓栫晫') == 123

    def test_deep_get_non_dict(self):
        # `d` is not a dict/list, e.g. int or None
        assert deep_get(1, 'a') is None
        assert deep_get(None, 'a', default='miss') == 'miss'

    def test_deep_get_non_iterable_keys(self):
        # `keys` is not iterable, e.g. int or None
        d = {'a': 1}
        assert deep_get(d, 123) is None
        assert deep_get(d, None) is None

    def test_deep_get_none_value(self):
        # A key exists with value None, should return None (not default)
        d = {'a': {'b': None}}
        assert deep_get(d, 'a.b', default='miss') is None

    def test_deep_get_falsy_value(self):
        # Existing falsy values should be returned as-is
        d = {'a': {'b': 0, 'c': False, 'd': '', 'e': []}}
        assert deep_get(d, 'a.b') == 0
        assert deep_get(d, 'a.c') is False
        assert deep_get(d, 'a.d') == ''
        assert deep_get(d, 'a.e') == []

    def test_deep_get_unhashable_key(self):
        # Key path containing an unhashable object raises TypeError -> default
        d = {'a': 1}
        assert deep_get(d, [{'a': 1}]) is None
        assert deep_get(d, [['a']]) is None

    def test_deep_get_returns_reference(self):
        # deep_get returns the inner object by reference, not a copy
        d = {'a': {'b': [1, 2]}}
        assert deep_get(d, 'a.b') is d['a']['b']

    def test_deep_get_tuple_keys(self):
        # keys can be a tuple
        d = {'a': {'b': 1}}
        assert deep_get(d, ('a', 'b')) == 1
        assert deep_get(d, ('a', 'x'), default='miss') == 'miss'
        assert deep_get_with_error(d, ('a', 'b')) == 1
        assert deep_exist(d, ('a', 'b')) is True
        assert deep_exist(d, ('a', 'x')) is False

    def test_deep_get_deque_keys(self):
        # keys can be a deque
        d = {'a': {'b': 1}}
        assert deep_get(d, deque(['a', 'b'])) == 1
        assert deep_get(d, deque(['a', 'x']), default='miss') == 'miss'
        assert deep_get_with_error(d, deque(['a', 'b'])) == 1
        assert deep_exist(d, deque(['a', 'b'])) is True
        assert deep_exist(d, deque(['a', 'x'])) is False


class TestDeepGetWithError:
    def test_deep_get_with_error_basic(self):
        d = {'a': {'b': 1}}
        assert deep_get_with_error(d, 'a.b') == 1

    def test_deep_get_with_error_missing(self):
        d = {'a': {'b': 1}}
        with pytest.raises(KeyError):
            deep_get_with_error(d, 'a.c')
        with pytest.raises(KeyError):
            deep_get_with_error(d, 'x.b')

    def test_deep_get_with_error_list(self):
        d = [1, 2]
        assert deep_get_with_error(d, [0]) == 1
        with pytest.raises(KeyError):
            deep_get_with_error(d, [2])  # IndexError raised and caught as KeyError

    def test_deep_get_with_error_non_dict(self):
        # TypeError is converted to KeyError
        with pytest.raises(KeyError):
            deep_get_with_error(1, 'a')
        with pytest.raises(KeyError):
            deep_get_with_error(None, 'a')

    def test_deep_get_with_error_empty_keys(self):
        d = {'a': 1}
        assert deep_get_with_error(d, []) == d


class TestDeepExist:
    def test_deep_exist_basic(self):
        d = {'a': {'b': 1}}
        assert deep_exist(d, 'a.b') is True
        assert deep_exist(d, 'a.c') is False
        assert deep_exist(d, 'x.b') is False

    def test_deep_exist_list(self):
        d = [1, {'a': 2}]
        assert deep_exist(d, [0]) is True
        assert deep_exist(d, [1, 'a']) is True
        assert deep_exist(d, [2]) is False

    def test_deep_exist_empty_keys(self):
        d = {'a': 1}
        assert deep_exist(d, []) is True
        assert deep_exist(d, '') is False

    def test_deep_exist_non_dict(self):
        assert deep_exist(1, 'a') is False
        assert deep_exist(None, 'a') is False

    def test_deep_exist_none_value(self):
        # A key exists with value None, should still be True
        d = {'a': None}
        assert deep_exist(d, 'a') is True


