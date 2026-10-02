"""
Tests for the write functions in ``oas.ext.deep``:

- ``deep_set``: set a value into a nested dict, creating missing levels
- ``deep_set_no_replace``: like ``deep_set``, but a non-dict met on the key path
  raises TypeError instead of being replaced
- ``deep_default``: set a value only when the key does not exist
- ``dict_update``: safely update a dict
- ``dict_copy``: safely shallow-copy a dict

``deep_set``/``deep_default`` correct non-dict intermediate levels on the fly
(e.g. an int at an intermediate key is replaced by a dict), so callers should
always use the return value:

    d = deep_set(d, keys, value)
"""

from collections import deque

import pytest

from oas.ext.deep import deep_default, deep_set, deep_set_no_replace, deep_set_with_error, dict_copy, dict_update

# Non-dict value types used to exercise the override correction of deep_set()
NON_DICT_VALUES = [
    pytest.param(1, id='int'),
    pytest.param(1.5, id='float'),
    pytest.param('text', id='str'),
    pytest.param([1, 2], id='list'),
    pytest.param(object(), id='object'),
]

VALUE = 'value'


class TestDeepSet:
    def test_deep_set_basic(self):
        d = {'a': {'b': 1}}
        deep_set(d, 'a.b', 2)
        assert d == {'a': {'b': 2}}

    def test_deep_set_create(self):
        d = {}
        assert deep_set(d, 'a.b.c', 1) == {'a': {'b': {'c': 1}}}
        assert d == {'a': {'b': {'c': 1}}}

    def test_deep_set_list_keys(self):
        d = {}
        assert deep_set(d, ['a', 'b'], 1) == {'a': {'b': 1}}

    def test_deep_set_overwrite(self):
        d = {'a': 1}
        assert deep_set(d, 'a', 2) == {'a': 2}

    def test_deep_set_overwrite_path_multi(self):
        # Overwriting a deeper path where the intermediate is not a dict
        d = {'a': {'b': 1}}
        deep_set(d, 'a.b.c', 2)
        assert d == {'a': {'b': {'c': 2}}}

    def test_deep_set_correction_non_dict(self):
        # input d=1
        # a=2
        assert deep_set(1, 'a', 2) == {'a': 2}
        # a.b=2
        assert deep_set(1, 'a.b', 2) == {'a': {'b': 2}}
        # a.b.c=2
        assert deep_set(1, 'a.b.c', 2) == {'a': {'b': {'c': 2}}}
        # []=2
        # If keys is empty, implementation returns {} for non-dict input
        assert deep_set(1, [], 2) == {}

    def test_deep_set_correction_existing_dict(self):
        # input {a: 1}
        d = {'a': 1}
        # a=2
        assert deep_set(d.copy(), 'a', 2) == {'a': 2}
        # a.b=2
        # 'a' was 1 (int), should be corrected to dict
        assert deep_set(d.copy(), 'a.b', 2) == {'a': {'b': 2}}
        # a.b.c=2
        assert deep_set(d.copy(), 'a.b.c', 2) == {'a': {'b': {'c': 2}}}
        # []=2
        # keys=[] returns raw_d if raw_d is dict
        assert deep_set(d.copy(), [], 2) == {'a': 1}

    def test_deep_set_non_iterable_keys(self):
        # `keys` is not iterable, treated as empty keys
        d = {'a': 1}
        assert deep_set(d, 123, 2) == {'a': 1}
        assert deep_set(1, 123, 2) == {}

    def test_deep_set_none_value(self):
        d = {}
        assert deep_set(d, 'a.b', None) == {'a': {'b': None}}

    def test_deep_set_list_middle_corrected(self):
        # Write ops assume dict only: a list met on the key path is treated as
        # a dict and replaced. This is the expected behaviour, not an error.
        d = {'a': [1]}
        deep_set(d, 'a.0.b', 2)
        assert d == {'a': {'0': {'b': 2}}}

    def test_deep_set_unhashable_key(self):
        # A non-hashable key cannot be a dict key: return raw_d unchanged
        d = {'a': 1}
        assert deep_set(d, [['x']], 2) == {'a': 1}
        assert deep_set(d, [['x'], 'y'], 2) == {'a': 1}
        # Non-dict raw_d cannot be corrected either, return {}
        assert deep_set(1, [['x']], 2) == {}

    def test_deep_set_empty_keys_non_dict_containers(self):
        # keys=[] on a non-dict container returns {} (contract: returns dict)
        assert deep_set([1, 2], [], 3) == {}
        assert deep_set({1, 2}, [], 3) == {}
        assert deep_set('abc', [], 3) == {}

    def test_deep_set_returns_same_object(self):
        # When the root is a dict and keys is non-empty, the same object is returned
        d = {'a': {}}
        assert deep_set(d, 'a.b', 1) is d

    def test_deep_set_tuple_keys(self):
        # keys can be a tuple
        d = {}
        assert deep_set(d, ('a', 'b'), 1) == {'a': {'b': 1}}

    def test_deep_set_deque_keys(self):
        # keys can be a deque
        d = {}
        assert deep_set(d, deque(['a', 'b']), 1) == {'a': {'b': 1}}


class TestDeepDefault:
    def test_deep_default_existing(self):
        d = {'a': {'b': 1}}
        deep_default(d, 'a.b', 2)
        assert d == {'a': {'b': 1}}

    def test_deep_default_missing(self):
        d = {'a': {'b': 1}}
        deep_default(d, 'a.c', 2)
        assert d == {'a': {'b': 1, 'c': 2}}

    def test_deep_default_create(self):
        d = {}
        assert deep_default(d, 'a.b', 1) == {'a': {'b': 1}}

    def test_deep_default_correction_non_dict(self):
        # input d=1
        assert deep_default(1, 'a', 2) == {'a': 2}
        assert deep_default(1, 'a.b', 2) == {'a': {'b': 2}}
        assert deep_default(1, 'a.b.c', 2) == {'a': {'b': {'c': 2}}}
        assert deep_default(1, [], 2) == {}

    def test_deep_default_correction_existing_dict(self):
        # input {a: 1}
        d = {'a': 1}
        # a=2, key exists so value unchanged
        assert deep_default(d.copy(), 'a', 2) == {'a': 1}
        # a.b=2, 'a' was 1 (int), corrected to dict
        assert deep_default(d.copy(), 'a.b', 2) == {'a': {'b': 2}}
        # a.b.c=2
        assert deep_default(d.copy(), 'a.b.c', 2) == {'a': {'b': {'c': 2}}}
        # []=2
        assert deep_default(d.copy(), [], 2) == {'a': 1}

    def test_deep_default_none_value(self):
        # None counts as existing, so default does not overwrite it
        d = {'a': None}
        deep_default(d, 'a', 1)
        assert d == {'a': None}

    def test_deep_default_tuple_keys(self):
        # keys can be a tuple
        d = {}
        assert deep_default(d, ('a', 'b'), 1) == {'a': {'b': 1}}

    def test_deep_default_deque_keys(self):
        # keys can be a deque
        d = {}
        assert deep_default(d, deque(['a', 'b']), 1) == {'a': {'b': 1}}

    def test_deep_default_unhashable_key(self):
        # A non-hashable key cannot be a dict key: return raw_d unchanged
        d = {'a': 1}
        assert deep_default(d, [['x']], 2) == {'a': 1}
        assert deep_default(d, [['x'], 'y'], 2) == {'a': 1}
        # Non-dict raw_d cannot be corrected either, return {}
        assert deep_default(1, [['x']], 2) == {}

    def test_deep_default_empty_keys_non_dict_containers(self):
        # keys=[] on a non-dict container returns {} (contract: returns dict)
        assert deep_default([1, 2], [], 3) == {}
        assert deep_default({1, 2}, [], 3) == {}
        assert deep_default('abc', [], 3) == {}


class TestDictUpdate:
    def test_dict_update_basic(self):
        d = {'a': 1}
        assert dict_update(d, {'b': 2}) == {'a': 1, 'b': 2}

    def test_dict_update_invalid(self):
        assert dict_update(None, {'a': 1}) == {'a': 1}
        assert dict_update({'a': 1}, None) == {'a': 1}

    def test_dict_update_aggressive(self):
        # Update with self
        d = {'a': 1}
        assert dict_update(d, d) == d
        # Update with incompatible type
        assert dict_update({'a': 1}, 123) == {'a': 1}

    def test_dict_update_non_dict_d(self):
        # `d` is not a dict (AttributeError) -> return new
        assert dict_update(1, {'a': 1}) == {'a': 1}
        assert dict_update(None, None) is None

    def test_dict_update_new_not_dict(self):
        # `new` is not a dict (TypeError) -> return d
        assert dict_update({'a': 1}, [1, 2]) == {'a': 1}

    def test_dict_update_mutates_in_place(self):
        d = {'a': 1}
        ret = dict_update(d, {'b': 2})
        assert ret is d


class TestDictCopy:
    def test_dict_copy_basic(self):
        d = {'a': 1, 'b': {'c': 2}}
        ret = dict_copy(d)
        # Same content, but a new top-level dict
        assert ret == d
        assert ret is not d

    def test_dict_copy_shallow(self):
        # Nested dict is shared with the source: shallow copy
        d = {'a': {'b': 1}}
        ret = dict_copy(d)
        assert ret['a'] is d['a']
        # Mutating the copy does not affect the source
        ret['x'] = 2
        assert d == {'a': {'b': 1}}

    def test_dict_copy_empty(self):
        d = {}
        ret = dict_copy(d)
        assert ret == {}
        assert ret is not d

    def test_dict_copy_non_dict(self):
        # `d` is not a dict -> {}
        # list and set also implement copy(), but they are not dicts
        assert dict_copy(None) == {}
        assert dict_copy(1) == {}
        assert dict_copy('text') == {}
        assert dict_copy([1, 2]) == {}
        assert dict_copy({1, 2}) == {}
        assert dict_copy(object()) == {}


class TestDeepSetOverrideNonDict:
    """
    deep_set() assumes dict on the whole key path, so any non-dict value met on
    the path is replaced by a dict. This matrix exercises the override for
    every non-dict depth (0=root .. 4) against every non-dict value type,
    setting 4 deeper levels in each function.
    """

    @pytest.mark.parametrize('non_dict_value', NON_DICT_VALUES)
    def test_depth_0_override(self, non_dict_value):
        # Root (depth 0) is non dict
        # set depth 1
        assert deep_set(non_dict_value, ['k1'], VALUE) == {'k1': VALUE}
        # set depth 2
        assert deep_set(non_dict_value, ['k1', 'k2'], VALUE) == {'k1': {'k2': VALUE}}
        # set depth 3
        assert deep_set(non_dict_value, ['k1', 'k2', 'k3'], VALUE) == {'k1': {'k2': {'k3': VALUE}}}
        # set depth 4
        assert deep_set(non_dict_value, ['k1', 'k2', 'k3', 'k4'], VALUE) == {
            'k1': {'k2': {'k3': {'k4': VALUE}}}
        }

    @pytest.mark.parametrize('non_dict_value', NON_DICT_VALUES)
    def test_depth_1_override(self, non_dict_value):
        # Depth 1 is non dict
        # set depth 1, override the non dict itself
        d = {'k1': non_dict_value}
        assert deep_set(d, ['k1'], VALUE) == {'k1': VALUE}
        # override depth 1, set depth 2
        d = {'k1': non_dict_value}
        assert deep_set(d, ['k1', 'k2'], VALUE) == {'k1': {'k2': VALUE}}
        # override depth 1, set depth 3
        d = {'k1': non_dict_value}
        assert deep_set(d, ['k1', 'k2', 'k3'], VALUE) == {'k1': {'k2': {'k3': VALUE}}}
        # override depth 1, set depth 4
        d = {'k1': non_dict_value}
        assert deep_set(d, ['k1', 'k2', 'k3', 'k4'], VALUE) == {
            'k1': {'k2': {'k3': {'k4': VALUE}}}
        }

    @pytest.mark.parametrize('non_dict_value', NON_DICT_VALUES)
    def test_depth_2_override(self, non_dict_value):
        # Depth 2 is non dict
        # set depth 2, override the non dict itself
        d = {'k1': {'k2': non_dict_value}}
        assert deep_set(d, ['k1', 'k2'], VALUE) == {'k1': {'k2': VALUE}}
        # override depth 2, set depth 3
        d = {'k1': {'k2': non_dict_value}}
        assert deep_set(d, ['k1', 'k2', 'k3'], VALUE) == {'k1': {'k2': {'k3': VALUE}}}
        # override depth 2, set depth 4
        d = {'k1': {'k2': non_dict_value}}
        assert deep_set(d, ['k1', 'k2', 'k3', 'k4'], VALUE) == {
            'k1': {'k2': {'k3': {'k4': VALUE}}}
        }
        # override depth 2, set depth 5
        d = {'k1': {'k2': non_dict_value}}
        assert deep_set(d, ['k1', 'k2', 'k3', 'k4', 'k5'], VALUE) == {
            'k1': {'k2': {'k3': {'k4': {'k5': VALUE}}}}
        }

    @pytest.mark.parametrize('non_dict_value', NON_DICT_VALUES)
    def test_depth_3_override(self, non_dict_value):
        # Depth 3 is non dict
        # set depth 3, override the non dict itself
        d = {'k1': {'k2': {'k3': non_dict_value}}}
        assert deep_set(d, ['k1', 'k2', 'k3'], VALUE) == {'k1': {'k2': {'k3': VALUE}}}
        # override depth 3, set depth 4
        d = {'k1': {'k2': {'k3': non_dict_value}}}
        assert deep_set(d, ['k1', 'k2', 'k3', 'k4'], VALUE) == {
            'k1': {'k2': {'k3': {'k4': VALUE}}}
        }
        # override depth 3, set depth 5
        d = {'k1': {'k2': {'k3': non_dict_value}}}
        assert deep_set(d, ['k1', 'k2', 'k3', 'k4', 'k5'], VALUE) == {
            'k1': {'k2': {'k3': {'k4': {'k5': VALUE}}}}
        }
        # override depth 3, set depth 6
        d = {'k1': {'k2': {'k3': non_dict_value}}}
        assert deep_set(d, ['k1', 'k2', 'k3', 'k4', 'k5', 'k6'], VALUE) == {
            'k1': {'k2': {'k3': {'k4': {'k5': {'k6': VALUE}}}}}
        }

    @pytest.mark.parametrize('non_dict_value', NON_DICT_VALUES)
    def test_depth_4_override(self, non_dict_value):
        # Depth 4 is non dict
        # set depth 4, override the non dict itself
        d = {'k1': {'k2': {'k3': {'k4': non_dict_value}}}}
        assert deep_set(d, ['k1', 'k2', 'k3', 'k4'], VALUE) == {'k1': {'k2': {'k3': {'k4': VALUE}}}}
        # override depth 4, set depth 5
        d = {'k1': {'k2': {'k3': {'k4': non_dict_value}}}}
        assert deep_set(d, ['k1', 'k2', 'k3', 'k4', 'k5'], VALUE) == {
            'k1': {'k2': {'k3': {'k4': {'k5': VALUE}}}}
        }
        # override depth 4, set depth 6
        d = {'k1': {'k2': {'k3': {'k4': non_dict_value}}}}
        assert deep_set(d, ['k1', 'k2', 'k3', 'k4', 'k5', 'k6'], VALUE) == {
            'k1': {'k2': {'k3': {'k4': {'k5': {'k6': VALUE}}}}}
        }
        # override depth 4, set depth 7
        d = {'k1': {'k2': {'k3': {'k4': non_dict_value}}}}
        assert deep_set(d, ['k1', 'k2', 'k3', 'k4', 'k5', 'k6', 'k7'], VALUE) == {
            'k1': {'k2': {'k3': {'k4': {'k5': {'k6': {'k7': VALUE}}}}}}
        }


class TestDeepSetWithError:
    """
    deep_set_with_error() writes strictly like deep_pop() reads: the whole key
    path must already exist as dicts. Missing keys raise KeyError, non-dict
    levels raise TypeError, and nothing is auto-created or repaired.
    """

    def test_deep_set_with_error_basic(self):
        d = {'a': {'b': 1}}
        assert deep_set_with_error(d, 'a.b', 2) == {'a': {'b': 2}}
        assert d == {'a': {'b': 2}}

    def test_deep_set_with_error_missing_key_raises(self):
        # Missing intermediate key is not created, raises KeyError
        d = {}
        with pytest.raises(KeyError):
            deep_set_with_error(d, 'a.b', 1)
        assert d == {}
        # Missing last key raises KeyError
        d = {'a': {}}
        with pytest.raises(KeyError):
            deep_set_with_error(d, 'a.b', 1)
        assert d == {'a': {}}

    def test_deep_set_with_error_returns_same_object(self):
        d = {'a': {'b': 1}}
        assert deep_set_with_error(d, 'a.b', 2) is d

    @pytest.mark.parametrize('non_dict_value', NON_DICT_VALUES)
    def test_deep_set_with_error_middle_non_dict_raises(self, non_dict_value):
        # An existing non-dict intermediate level is an error, not repaired
        d = {'a': non_dict_value}
        with pytest.raises(TypeError):
            deep_set_with_error(d, 'a.b', 2)
        # data unchanged
        assert d == {'a': non_dict_value}

    def test_deep_set_with_error_last_non_dict_raises(self):
        d = {'a': 1}
        with pytest.raises(TypeError):
            deep_set_with_error(d, 'a.b', 2)
        assert d == {'a': 1}

    def test_deep_set_with_error_empty_keys(self):
        d = {'a': 1}
        with pytest.raises(IndexError):
            deep_set_with_error(d, [], 2)
        assert d == {'a': 1}

    def test_deep_set_with_error_non_iterable_keys_raises(self):
        with pytest.raises(TypeError):
            deep_set_with_error({'a': 1}, 123, 2)

    def test_deep_set_with_error_tuple_deque_keys(self):
        d = {'a': {'b': 1}}
        assert deep_set_with_error(d, ('a', 'b'), 2) == {'a': {'b': 2}}
        d = {'a': {'b': 1}}
        assert deep_set_with_error(d, deque(['a', 'b']), 2) == {'a': {'b': 2}}


class TestDeepSetNoReplace:
    """
    deep_set_no_replace() creates missing levels like deep_set(), but a level
    that is not a dict is never replaced: the write is attempted eagerly and a
    TypeError telling the key and the value at it is raised instead. The value
    at the last key is the only thing overwritten.
    """

    def test_deep_set_no_replace_basic(self):
        d = {'a': {'b': 1}}
        assert deep_set_no_replace(d, 'a.b', 2) == {'a': {'b': 2}}
        assert d == {'a': {'b': 2}}

    def test_deep_set_no_replace_create(self):
        d = {}
        assert deep_set_no_replace(d, 'a.b.c', 1) == {'a': {'b': {'c': 1}}}
        assert d == {'a': {'b': {'c': 1}}}

    def test_deep_set_no_replace_returns_same_object(self):
        # The root object is always returned, non-dict levels are never rebuilt
        d = {}
        assert deep_set_no_replace(d, 'a.b', 1) is d
        d = {'a': {}}
        assert deep_set_no_replace(d, 'a.b', 1) is d

    def test_deep_set_no_replace_overwrite_last_key(self):
        # The value at the last key is overwritten, whatever it was
        d = {'a': 1}
        assert deep_set_no_replace(d, 'a', 2) == {'a': 2}
        d = {'a': {'b': 1}}
        assert deep_set_no_replace(d, 'a.b', 2) == {'a': {'b': 2}}
        # A dict at the last key is the value to overwrite, not a level of the
        # key path, so it is replaced
        d = {'a': {'b': {'c': 1}}}
        assert deep_set_no_replace(d, 'a.b', 2) == {'a': {'b': 2}}

    def test_deep_set_no_replace_none_value(self):
        d = {}
        assert deep_set_no_replace(d, 'a.b', None) == {'a': {'b': None}}

    def test_deep_set_no_replace_tuple_deque_keys(self):
        d = {'a': {'b': 1}}
        assert deep_set_no_replace(d, ('a', 'b'), 2) == {'a': {'b': 2}}
        d = {'a': {'b': 1}}
        assert deep_set_no_replace(d, deque(['a', 'b']), 2) == {'a': {'b': 2}}

    @pytest.mark.parametrize('non_dict_value', NON_DICT_VALUES)
    def test_deep_set_no_replace_root_non_dict_raises(self, non_dict_value):
        # deep_set() would rebuild a non-dict root, here the write fails
        with pytest.raises(TypeError):
            deep_set_no_replace(non_dict_value, 'a', 2)
        # Empty keys is an error before the root is written
        with pytest.raises(IndexError):
            deep_set_no_replace(non_dict_value, [], 2)

    @pytest.mark.parametrize('non_dict_value', NON_DICT_VALUES)
    def test_deep_set_no_replace_middle_non_dict_raises(self, non_dict_value):
        # A non-dict level of the key path is an error, not replaced
        d = {'a': non_dict_value}
        with pytest.raises(TypeError):
            deep_set_no_replace(d, 'a.b', 2)
        assert d == {'a': non_dict_value}
        d = {'a': {'b': non_dict_value}}
        with pytest.raises(TypeError):
            deep_set_no_replace(d, 'a.b.c', 2)
        assert d == {'a': {'b': non_dict_value}}
        d = {'a': {'b': {'c': non_dict_value}}}
        with pytest.raises(TypeError):
            deep_set_no_replace(d, 'a.b.c.d', 2)
        assert d == {'a': {'b': {'c': non_dict_value}}}

    def test_deep_set_no_replace_none_middle_raises(self):
        # None is not a dict, it must not be treated as a missing key
        d = {'a': None}
        with pytest.raises(TypeError):
            deep_set_no_replace(d, 'a.b', 2)
        assert d == {'a': None}

    def test_deep_set_no_replace_list_middle_raises(self):
        # Write ops are duck typed: a list indexed by the str key of a 'a.0.b'
        # key path is an error
        d = {'a': [1]}
        with pytest.raises(TypeError):
            deep_set_no_replace(d, 'a.0.b', 2)
        assert d == {'a': [1]}

    def test_deep_set_no_replace_list_int_index(self):
        # Write ops are duck typed: a list indexed by int works like deep_get(),
        # the list is written through, not replaced by a dict
        d = {'a': [1, 2]}
        assert deep_set_no_replace(d, ['a', 0], 3) == {'a': [3, 2]}
        assert d == {'a': [3, 2]}

    def test_deep_set_no_replace_dict_subclass(self):
        # Write ops are duck typed, a dict subclass stays usable as a level
        class MyDict(dict):
            pass

        d = MyDict(a=MyDict(b=1))
        assert deep_set_no_replace(d, 'a.b', 2) is d
        assert d == {'a': {'b': 2}}
        # A missing level is still created as a plain dict
        d = MyDict(a=MyDict())
        deep_set_no_replace(d, 'a.b.c', 1)
        assert d == {'a': {'b': {'c': 1}}}
        assert type(d['a']['b']) is dict

    def test_deep_set_no_replace_non_iterable_keys_raises(self):
        with pytest.raises(TypeError):
            deep_set_no_replace({'a': 1}, 123, 2)

    def test_deep_set_no_replace_unhashable_key_raises(self):
        # A non-hashable key cannot be a dict key: deep_set() returns raw_d,
        # here it is an error
        d = {'a': 1}
        with pytest.raises(TypeError):
            deep_set_no_replace(d, [['x']], 2)
        assert d == {'a': 1}
        d = {'a': 1}
        with pytest.raises(TypeError):
            deep_set_no_replace(d, [['x'], 'y'], 2)
        assert d == {'a': 1}
        # Levels before the error have been created, `d` is partially modified
        d = {}
        with pytest.raises(TypeError):
            deep_set_no_replace(d, ['a', 'b', ['x']], 2)
        assert d == {'a': {'b': {}}}

    def test_deep_set_no_replace_empty_keys_raises(self):
        d = {'a': 1}
        with pytest.raises(IndexError):
            deep_set_no_replace(d, [], 2)
        assert d == {'a': 1}

    @pytest.mark.parametrize('non_dict_value, expected', [
        (1, "deep_set_no_replace() expected dict at key 'a', got int: 1"),
        (1.5, "deep_set_no_replace() expected dict at key 'a', got float: 1.5"),
        ('text', "deep_set_no_replace() expected dict at key 'a', got str: 'text'"),
        ([1, 2], "deep_set_no_replace() expected dict at key 'a', got list: [1, 2]"),
        (None, "deep_set_no_replace() expected dict at key 'a', got NoneType: None"),
    ])
    def test_deep_set_no_replace_error_message(self, non_dict_value, expected):
        # The message tells which key is not a dict and the value at it
        d = {'a': non_dict_value}
        with pytest.raises(TypeError) as e:
            deep_set_no_replace(d, 'a.b', 2)
        assert str(e.value) == expected
        assert d == {'a': non_dict_value}
        # The TypeError of python is chained
        assert e.value.__cause__ is not None

    def test_deep_set_no_replace_error_message_lookup(self):
        # The error can be raised when stepping into a deeper level
        d = {'a': 1}
        with pytest.raises(TypeError) as e:
            deep_set_no_replace(d, 'a.b.c', 2)
        assert str(e.value) == "deep_set_no_replace() expected dict at key 'a', got int: 1"
        assert d == {'a': 1}

    def test_deep_set_no_replace_error_message_deep(self):
        # The key of the message is the last one that is not a dict
        d = {'a': {'b': 1}}
        with pytest.raises(TypeError) as e:
            deep_set_no_replace(d, 'a.b.c', 2)
        assert str(e.value) == "deep_set_no_replace() expected dict at key 'b', got int: 1"
        assert d == {'a': {'b': 1}}

    def test_deep_set_no_replace_error_message_root(self):
        # The root has no key, so the message does not have one
        with pytest.raises(TypeError) as e:
            deep_set_no_replace(1, 'a', 2)
        assert str(e.value) == 'deep_set_no_replace() expected dict, got int: 1'

    def test_deep_set_no_replace_error_message_truncate(self):
        # A huge value is truncated, the message stays readable
        value = list(range(1000))
        d = {'a': value}
        with pytest.raises(TypeError) as e:
            deep_set_no_replace(d, 'a.b', 2)
        assert str(e.value) == (
            f"deep_set_no_replace() expected dict at key 'a', got list: {repr(value)[:200]}...")
        assert d == {'a': value}

    @pytest.mark.parametrize('length, truncated', [
        # repr of 'x' * length is `length + 2` characters long
        (198, False),
        (199, True),
    ])
    def test_deep_set_no_replace_error_message_truncate_boundary(self, length, truncated):
        # A value at the limit is kept as is, only a longer one is truncated
        value = 'x' * length
        d = {'a': value}
        with pytest.raises(TypeError) as e:
            deep_set_no_replace(d, 'a.b', 2)
        head = "deep_set_no_replace() expected dict at key 'a', got str: "
        expected = f'{head}{value!r}'
        if truncated:
            expected = f'{expected[:len(head) + 200]}...'
        assert str(e.value) == expected

    def test_deep_set_no_replace_unhashable_key_message(self):
        # A non-hashable key cannot be a dict key, the python message is kept
        with pytest.raises(TypeError) as e:
            deep_set_no_replace({'a': 1}, [['x'], 'y'], 2)
        assert "unhashable type: 'list'" in str(e.value)

    def test_deep_set_no_replace_non_iterable_keys_message(self):
        # `keys` is not iterable, the python message is kept
        with pytest.raises(TypeError) as e:
            deep_set_no_replace({'a': 1}, 123, 2)
        assert str(e.value) == "'int' object is not iterable"

    def test_deep_set_no_replace_contrast_with_deep_set(self):
        # deep_set() repairs a non-dict level, deep_set_no_replace() refuses
        assert deep_set({'a': 1}, 'a.b', 2) == {'a': {'b': 2}}
        d = {'a': 1}
        with pytest.raises(TypeError):
            deep_set_no_replace(d, 'a.b', 2)
        assert d == {'a': 1}


