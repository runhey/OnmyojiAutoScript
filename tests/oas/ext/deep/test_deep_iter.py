"""
Tests for the iteration functions in ``oas.ext.deep``:

- Fixed-depth helpers: ``deep_iter_depth1``/``deep_keys_depth1``/
  ``deep_values_depth1`` and ``deep_iter_depth2``/``deep_keys_depth2``/
  ``deep_values_depth2``
- Depth iterators: ``deep_iter``/``deep_keys``/``deep_values``, unlimited when
  ``depth`` is None (the default)
- Diff/patch generators: ``deep_iter_diff``/``deep_iter_patch``

All iterators suppress errors on non-dict input. An unlimited iteration (no
``depth``) is bounded by ``max_recursion``, deeper data raises ``RecursionError``
instead of looping forever on a circular reference.
"""

import pytest

from oas.ext.deep import (
    OP_ADD, OP_DEL, OP_SET, deep_iter, deep_iter_depth1, deep_iter_depth2, deep_iter_diff, deep_iter_patch, deep_keys,
    deep_keys_depth1, deep_keys_depth2, deep_values, deep_values_depth1, deep_values_depth2
)

COMPLEX_DICT = {
    'a': 1,
    'b': {
        'c': 2,
        'd': {
            'e': 3,
            'f': {'f1': 4}
        },
        'g': 5
    },
    'h': {
        'i': 6
    },
    'j': 7,
    'k': [8, 9]
}


def build_chain(n_dict):
    """
    A chain of `n_dict` dicts, with a leaf value at the bottom, used to test
    the depth limit of an unlimited iteration
    """
    d = {}
    cur = d
    for _ in range(n_dict):
        cur['k'] = {}
        cur = cur['k']
    cur['leaf'] = 1
    return d


class TestDeepIterDepth1:
    def test_deep_iter_depth1(self):
        d = {'a': 1, 'b': 2}
        assert dict(deep_iter_depth1(d)) == d
        assert list(deep_iter_depth1(None)) == []
        assert list(deep_keys_depth1(d)) == ['a', 'b']
        assert list(deep_values_depth1(d)) == [1, 2]

    def test_deep_iter_depth1_non_dict(self):
        assert list(deep_iter_depth1([1, 2])) == []
        assert list(deep_keys_depth1(1)) == []
        assert list(deep_values_depth1(None)) == []


class TestDeepIterDepth2:
    def test_deep_iter_depth2(self):
        d = {'a': {'b': 1}, 'c': {'d': 2}}
        assert list(deep_iter_depth2(d)) == [('a', 'b', 1), ('c', 'd', 2)]
        assert list(deep_iter_depth2({'a': 1})) == []
        assert list(deep_keys_depth2(d)) == [('a', 'b'), ('c', 'd')]
        assert list(deep_values_depth2(d)) == [1, 2]

    def test_deep_iter_depth2_inconsistent(self):
        # Inconsistent depth levels
        d = {'a': {'b': 1}, 'c': 2, 'd': {'e': 3}}
        # deep_iter_depth2 should iterate a.b and d.e, skipping c
        res = list(deep_iter_depth2(d))
        assert ('a', 'b', 1) in res
        assert ('d', 'e', 3) in res
        assert len(res) == 2

    def test_deep_iter_depth2_non_dict(self):
        assert list(deep_iter_depth2(None)) == []
        assert list(deep_keys_depth2(1)) == []
        assert list(deep_values_depth2([1, 2])) == []


class TestDeepIter:
    def test_deep_iter_basic(self):
        d = {'a': {'b': {'c': 1}}}
        # tuple[key], value
        assert list(deep_iter(d, depth=3)) == [(('a', 'b', 'c'), 1)]
        assert list(deep_keys(d, depth=3)) == [('a', 'b', 'c')]
        assert list(deep_values(d, depth=3)) == [1]

    def test_deep_iter_depth1(self):
        d = {'a': 1, 'b': {'c': 2}}
        assert list(deep_iter(d, depth=1)) == [(('a',), 1), (('b',), {'c': 2})]
        assert list(deep_keys(d, depth=1)) == [('a',), ('b',)]
        assert list(deep_values(d, depth=1)) == [1, {'c': 2}]

    def test_deep_iter_min_depth(self):
        d = {'a': 1, 'b': {'c': 2}}
        res = list(deep_iter(d, min_depth=1, depth=2))
        assert (('a',), 1) in res
        assert (('b', 'c'), 2) in res

    def test_deep_iter_min_eq_depth(self):
        d = {'a': {'b': 1}}
        assert list(deep_iter(d, min_depth=2, depth=2)) == [(('a', 'b'), 1)]

    def test_deep_iter_aggressive(self):
        # Empty dict
        assert list(deep_iter({}, depth=3)) == []
        # depth < min_depth raises AssertionError
        with pytest.raises(AssertionError):
            list(deep_iter({}, min_depth=2, depth=1))
        # Non-dict
        assert list(deep_iter(None, depth=3)) == []
        assert list(deep_keys(None, depth=3)) == []
        assert list(deep_values(None, depth=3)) == []

    def test_deep_iter_circular(self):
        # deep_iter should be safe against circular references due to depth limit
        d = {}
        d['a'] = d
        # Should not infinite loop
        res = list(deep_iter(d, depth=5))
        # depth 1: (('a',), d)
        # depth 2: (('a', 'a'), d)
        # ...
        assert len(res) == 1
        assert res[0][0] == ('a',) * 5

    def test_deep_iter_complex(self):
        all_items = list(deep_iter(COMPLEX_DICT, min_depth=1, depth=4))

        expected_paths = [
            (('a',), 1),
            (('b', 'c'), 2),
            (('b', 'd', 'e'), 3),
            (('b', 'd', 'f', 'f1'), 4),
            (('b', 'g'), 5),
            (('h', 'i'), 6),
            (('j',), 7),
            (('k',), [8, 9])
        ]

        for path, val in expected_paths:
            assert (path, val) in all_items
        assert len(all_items) == len(expected_paths)

    def test_deep_iter_depth2(self):
        res = list(deep_iter(COMPLEX_DICT, depth=2))
        # b: c, d, g
        # h: i
        # only depth 2 items are yielded
        assert (('b', 'c'), 2) in res
        assert (('b', 'd'), {'e': 3, 'f': {'f1': 4}}) in res
        assert (('b', 'g'), 5) in res
        assert (('h', 'i'), 6) in res
        assert len(res) == 4

    def test_deep_iter_depth2_min1(self):
        res = list(deep_iter(COMPLEX_DICT, min_depth=1, depth=2))
        # a, j, k (depth 1)
        # b.c, b.d, b.g, h.i (depth 2)
        assert (('a',), 1) in res
        assert (('b', 'c'), 2) in res
        assert len(res) == 7

    def test_deep_iter_depth2_3(self):
        # min_depth=2, depth=3
        res = list(deep_iter(COMPLEX_DICT, min_depth=2, depth=3))
        # Depth 2: b.c, b.g, h.i
        # Depth 3: b.d.e, b.d.f
        assert (('b', 'c'), 2) in res
        assert (('b', 'd', 'e'), 3) in res
        # b.d.f is dict, so it's not yielded if current < depth?
        # current=2: b.d is dict, added to q.
        # current=3: b.d.e (yield), b.d.f (yield as it's the target depth)
        assert (('b', 'd', 'f'), {'f1': 4}) in res
        assert len(res) == 5


class TestDeepIterUnlimited:
    """
    depth=None (the default) iterates without a depth limit, min_depth defaults
    to 1 then, so values of all depths are yielded. An unlimited iteration is
    bounded by max_recursion (1000 by default, the recursion limit of python),
    a deeper dict or a circular reference raises RecursionError.
    """

    DATA = {'a': 1, 'b': {'c': 2, 'd': {'e': 3}}}

    def test_deep_iter_unlimited(self):
        assert list(deep_iter(self.DATA)) == [
            (('a',), 1),
            (('b', 'c'), 2),
            (('b', 'd', 'e'), 3),
        ]

    def test_deep_iter_unlimited_complex(self):
        # Values of all depths are yielded, level by level (BFS)
        assert list(deep_iter(COMPLEX_DICT)) == [
            (('a',), 1),
            (('j',), 7),
            (('k',), [8, 9]),
            (('b', 'c'), 2),
            (('b', 'g'), 5),
            (('h', 'i'), 6),
            (('b', 'd', 'e'), 3),
            (('b', 'd', 'f', 'f1'), 4),
        ]

    def test_deep_iter_unlimited_min_depth(self):
        # min_depth works the same as with a depth limit
        assert list(deep_iter(self.DATA, min_depth=2)) == [
            (('b', 'c'), 2),
            (('b', 'd', 'e'), 3),
        ]

    def test_deep_keys_unlimited(self):
        assert list(deep_keys(self.DATA)) == [('a',), ('b', 'c'), ('b', 'd', 'e')]

    def test_deep_values_unlimited(self):
        assert list(deep_values(self.DATA)) == [1, 2, 3]

    def test_deep_iter_unlimited_assert(self):
        # min_depth must be >= 1
        with pytest.raises(AssertionError):
            list(deep_iter({}, min_depth=0))

    def test_deep_iter_unlimited_non_dict(self):
        assert list(deep_iter(None)) == []
        assert list(deep_keys(None)) == []
        assert list(deep_values(None)) == []

    def test_deep_iter_unlimited_empty_dict(self):
        # An empty dict has nothing to yield, it is stepped into and dropped
        assert list(deep_iter({'a': {}, 'b': 1})) == [(('b',), 1)]
        assert list(deep_keys({'a': {}, 'b': 1})) == [('b',)]
        assert list(deep_values({'a': {}, 'b': 1})) == [1]

    def test_deep_iter_unlimited_shared_dict(self):
        # A dict met twice is stepped into twice, the same as with a depth limit
        shared = {'x': 1}
        d = {'a': shared, 'b': shared}
        assert list(deep_iter(d)) == [(('a', 'x'), 1), (('b', 'x'), 1)]
        assert list(deep_keys(d)) == [('a', 'x'), ('b', 'x')]
        assert list(deep_values(d)) == [1, 1]
        assert list(deep_iter(d, min_depth=2, depth=2)) == [(('a', 'x'), 1), (('b', 'x'), 1)]

    def test_deep_iter_unlimited_circular_raises(self):
        # A circular reference raises instead of looping forever
        d = {}
        d['a'] = d
        with pytest.raises(RecursionError):
            list(deep_iter(d))
        with pytest.raises(RecursionError):
            list(deep_keys(d))
        with pytest.raises(RecursionError):
            list(deep_values(d))
        # A `depth` bounds the iteration, no error is raised
        assert list(deep_iter(d, min_depth=3, depth=3)) == [(('a', 'a', 'a'), d)]

    def test_deep_iter_unlimited_deep_data(self):
        # A deep dict within max_recursion is fully iterated
        d = build_chain(90)
        assert list(deep_iter(d)) == [(('k',) * 90 + ('leaf',), 1)]

    def test_deep_iter_max_recursion_default(self):
        # max_recursion defaults to 1000, the default recursion limit of python
        assert list(deep_iter(build_chain(999))) == [(('k',) * 999 + ('leaf',), 1)]
        with pytest.raises(RecursionError):
            list(deep_iter(build_chain(1000)))

    def test_deep_iter_unlimited_deeper_than_max_raises(self):
        # Data deeper than max_recursion raises, give a bigger one to iterate it
        d = build_chain(15)
        with pytest.raises(RecursionError):
            list(deep_iter(d, max_recursion=10))
        with pytest.raises(RecursionError):
            list(deep_keys(d, max_recursion=10))
        with pytest.raises(RecursionError):
            list(deep_values(d, max_recursion=10))
        # A bigger max_recursion iterates the whole chain
        assert list(deep_iter(d, max_recursion=16)) == [(('k',) * 15 + ('leaf',), 1)]
        # An explicit `depth` is not bounded by max_recursion
        assert list(deep_iter(d, depth=16)) == [(('k',) * 15 + ('leaf',), 1)]


class TestDeepIterDiff:
    def test_deep_iter_diff_basic(self):
        d1 = {'a': 1, 'b': {'c': 2}}
        d2 = {'a': 2, 'b': {'c': 2, 'd': 3}}
        diff = list(deep_iter_diff(d1, d2))
        # path, val_before, val_after
        assert (('a',), 1, 2) in diff
        assert (('b', 'd'), None, 3) in diff

    def test_deep_iter_diff_identical(self):
        d = {'a': 1, 'b': {'c': 2}}
        assert list(deep_iter_diff(d, {'a': 1, 'b': {'c': 2}})) == []

    def test_deep_iter_diff_non_dict(self):
        assert list(deep_iter_diff({'a': 1}, 2)) == [((), {'a': 1}, 2)]
        assert list(deep_iter_diff(1, {'a': 2})) == [((), 1, {'a': 2})]

    def test_deep_iter_diff_nested_non_dict(self):
        # Test when nested values have different types
        d1 = {'a': {'b': 1}}
        d2 = {'a': 2}
        diff = list(deep_iter_diff(d1, d2))
        assert (('a',), {'b': 1}, 2) in diff

    def test_deep_iter_diff_deleted(self):
        d1 = {'a': 1, 'b': 2}
        d2 = {'a': 1}
        diff = list(deep_iter_diff(d1, d2))
        assert (('b',), 2, None) in diff

    def test_deep_iter_diff_equal_value_different_type(self):
        # [1, 2] != (1, 2), and neither is a dict -> reported as a diff
        d1 = {'a': [1, 2]}
        d2 = {'a': (1, 2)}
        assert list(deep_iter_diff(d1, d2)) == [(('a',), [1, 2], (1, 2))]

    def test_deep_iter_diff_circular(self):
        # Circular references must not raise RecursionError or loop forever
        d1 = {}
        d1['a'] = d1
        d2 = {}
        d2['a'] = d2
        assert list(deep_iter_diff(d1, d2)) == []

    def test_deep_iter_diff_circular_partial(self):
        # Circular reference in one side still yields non-circular diffs
        d1 = {}
        d1['a'] = d1
        d1['x'] = 1
        d2 = {}
        d2['a'] = d2
        d2['x'] = 2
        diff = list(deep_iter_diff(d1, d2))
        assert (('x',), 1, 2) in diff

    def test_deep_iter_diff_deep_equal(self):
        # Very deep nested equal dicts must not raise RecursionError
        d1 = cur1 = {}
        d2 = cur2 = {}
        for _ in range(1100):
            cur1['k'] = {}
            cur1 = cur1['k']
            cur2['k'] = {}
            cur2 = cur2['k']
        cur1['v'] = 1
        cur2['v'] = 1
        assert list(deep_iter_diff(d1, d2)) == []


class TestDeepIterPatch:
    def test_deep_iter_patch_basic(self):
        before = {'a': 1, 'b': 2}
        after = {'a': 1, 'c': 3}
        patch = list(deep_iter_patch(before, after))
        # op, path, val_after
        assert (OP_DEL, ('b',), None) in patch
        assert (OP_ADD, ('c',), 3) in patch

    def test_deep_iter_patch_identical(self):
        d = {'a': 1}
        assert list(deep_iter_patch(d, {'a': 1})) == []

    def test_deep_iter_patch_non_dict(self):
        assert list(deep_iter_patch({'a': 1}, 2)) == [(OP_SET, (), 2)]

    def test_deep_iter_patch_set(self):
        before = {'a': 1}
        after = {'a': 2}
        assert list(deep_iter_patch(before, after)) == [(OP_SET, ('a',), 2)]

    def test_deep_iter_patch_nested_add(self):
        before = {'a': {'b': 1}}
        after = {'a': {'b': 1, 'c': 2}}
        assert list(deep_iter_patch(before, after)) == [(OP_ADD, ('a', 'c'), 2)]

    def test_deep_iter_patch_nested_del(self):
        before = {'a': {'b': 1, 'c': 2}}
        after = {'a': {'b': 1}}
        assert list(deep_iter_patch(before, after)) == [(OP_DEL, ('a', 'c'), None)]

    def test_deep_iter_patch_circular(self):
        # Circular references must not raise RecursionError or loop forever
        d1 = {}
        d1['a'] = d1
        d2 = {}
        d2['a'] = d2
        assert list(deep_iter_patch(d1, d2)) == []

    def test_deep_iter_patch_deep_equal(self):
        # Very deep nested equal dicts must not raise RecursionError
        d1 = cur1 = {}
        d2 = cur2 = {}
        for _ in range(1100):
            cur1['k'] = {}
            cur1 = cur1['k']
            cur2['k'] = {}
            cur2 = cur2['k']
        cur1['v'] = 1
        cur2['v'] = 1
        assert list(deep_iter_patch(d1, d2)) == []


