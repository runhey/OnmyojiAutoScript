"""
Tests for oas.backport.listify

listify flattens potentially nested structures into a flat list.
"""
from collections import deque

import pytest

from oas.backport.listify import _iter_item, listify


class TestListifyAtomic:
    """Tests for atomic (non-iterable or non-flattened) inputs"""

    @pytest.mark.parametrize("item, expected", [
        (42, [42]),
        (0, [0]),
        (-1, [-1]),
        (3.14, [3.14]),
        (True, [True]),
        (False, [False]),
        (None, [None]),
        ("hello", ["hello"]),
        ("", [""]),
        (b"bytes", [b"bytes"]),
        (b"", [b""]),
        ({"a": 1}, [{"a": 1}]),
        ({}, [{}]),
    ])
    def test_atomic_items(self, item, expected):
        """Atomic items should be wrapped in a single-element list"""
        assert listify(item) == expected

    def test_dict_is_atomic_regardless_of_content(self):
        """Dict is treated as atomic, not flattened into key-value pairs"""
        d = {"a": [1, 2], "b": 3}
        result = listify(d)
        assert result == [d]


class TestListifyListLike:
    """Tests for list-like types: list, tuple, set, deque, frozenset"""

    def test_flat_list(self):
        """Flat list should be returned as-is"""
        assert listify([1, 2, 3]) == [1, 2, 3]

    def test_flat_tuple(self):
        """Flat tuple should be flattened to list"""
        assert listify((1, 2, 3)) == [1, 2, 3]

    def test_flat_set(self):
        """Flat set should be flattened to list (order not guaranteed)"""
        result = listify({1, 2, 3})
        assert sorted(result) == [1, 2, 3]

    def test_flat_deque(self):
        """Flat deque should be flattened to list"""
        result = listify(deque([1, 2, 3]))
        assert result == [1, 2, 3]

    def test_flat_frozenset(self):
        """Flat frozenset should be flattened to list"""
        result = listify(frozenset([1, 2, 3]))
        assert sorted(result) == [1, 2, 3]

    def test_single_level_nesting(self):
        """Single level of nesting should be flattened"""
        assert listify([1, [2, 3], 4]) == [1, 2, 3, 4]

    def test_deep_nesting(self):
        """Deeply nested structures should be fully flattened"""
        assert listify([1, [2, [3, [4]]]]) == [1, 2, 3, 4]

    def test_mixed_types_nested(self):
        """Nested structures with mixed atomic types should flatten correctly"""
        assert listify([1, "abc", [2, "def"]]) == [1, "abc", 2, "def"]

    def test_nested_tuple_in_list(self):
        """Nested tuple in list should be flattened"""
        assert listify([1, (2, 3), 4]) == [1, 2, 3, 4]

    def test_nested_set_in_list(self):
        """Nested set in list should be flattened"""
        result = listify([1, {2, 3}, 4])
        # set order is not guaranteed
        assert result[0] == 1
        assert sorted(result[1:3]) == [2, 3]
        assert result[3] == 4

    @pytest.mark.parametrize("nested, expected", [
        ([[[1]]], [1]),
        ([[1, [2]], [3]], [1, 2, 3]),
        ([(), [(), [()]]], []),
    ])
    def test_various_nesting_patterns(self, nested, expected):
        """Various nesting patterns should all flatten completely"""
        assert listify(nested) == expected

    def test_empty_list_like(self):
        """Empty list-like containers should return empty list"""
        assert listify([]) == []
        assert listify(()) == []
        assert listify(set()) == []
        assert listify(deque()) == []
        assert listify(frozenset()) == []

    def test_nested_empty_containers(self):
        """Nested empty containers should be filtered out"""
        assert listify([[], [[]], [[], []]]) == []

    def test_dict_inside_list(self):
        """Dict inside a list should be treated as atomic"""
        d = {"key": "value"}
        assert listify([1, d, 2]) == [1, d, 2]

    def test_str_inside_list(self):
        """String inside a list should be treated as atomic"""
        assert listify(["hello", "world"]) == ["hello", "world"]

    def test_bytes_inside_list(self):
        """Bytes inside a list should be treated as atomic"""
        assert listify([b"hello", b"world"]) == [b"hello", b"world"]


class TestListifyOtherIterable:
    """Tests for iterables that are not TYPE_LIST_LIKE: generator, range, etc."""

    def test_generator(self):
        """Generator expression should be flattened"""
        gen = (x for x in [1, [2, 3], 4])
        assert listify(gen) == [1, 2, 3, 4]

    def test_range(self):
        """Range object should be flattened"""
        assert listify(range(5)) == [0, 1, 2, 3, 4]

    def test_map_object(self):
        """Map object should be flattened"""
        result = listify(map(str, [1, 2, 3]))
        assert result == ["1", "2", "3"]

    def test_filter_object(self):
        """Filter object should be flattened"""
        result = listify(filter(lambda x: x > 1, [1, 2, 3]))
        assert result == [2, 3]

    def test_nested_generator_in_list(self):
        """Generator nested inside a list should be flattened"""
        def gen():
            yield 2
            yield 3
        assert listify([1, gen(), 4]) == [1, 2, 3, 4]

    def test_reversed(self):
        """reversed() object should be flattened"""
        assert listify(reversed([1, 2, 3])) == [3, 2, 1]


class TestListifyEdgeCases:
    """Tests for edge cases and special inputs"""

    def test_empty_iterator(self):
        """Empty iterator should return empty list"""
        assert listify(iter([])) == []

    def test_single_element_list(self):
        """Single-element list should unwrap"""
        assert listify([42]) == [42]

    def test_list_of_lists(self):
        """List of lists should flatten all levels"""
        assert listify([[1, 2], [3, 4], [5, 6]]) == [1, 2, 3, 4, 5, 6]

    def test_mixed_nested_structure(self):
        """Mixed deeply nested structure with various types"""
        result = listify([[1, "a"], {"b": 2}, (3, [4, {5}])])
        # first element: 1, second: "a", third: the dict (atomic), fourth: 3, fifth: 4, sixth: 5
        assert result[0] == 1
        assert result[1] == "a"
        assert isinstance(result[2], dict)
        assert result[3] == 3
        assert result[4] == 4
        assert result[5] == 5
        assert len(result) == 6


class TestListifyIdempotent:
    """Tests that listify is idempotent"""

    @pytest.mark.parametrize("item", [
        [1, 2, 3],
        [1, [2, 3]],
        [1, "abc", [2, "def"]],
        [],
        [{"a": 1}],
    ])
    def test_listify_of_listify(self, item):
        """listify(listify(x)) should equal listify(x)"""
        once = listify(item)
        twice = listify(once)
        assert once == twice


class TestIterItem:
    """Tests for the internal _iter_item generator"""

    def test_yields_atomic(self):
        """_iter_item should yield atomic items as a single-element generator"""
        assert list(_iter_item([42])) == [42]

    def test_yields_flattened(self):
        """_iter_item should yield flattened items for nested structures"""
        assert list(_iter_item([1, [2, 3]])) == [1, 2, 3]

    def test_yields_empty(self):
        """_iter_item on empty iterable should yield nothing"""
        assert list(_iter_item([])) == []

    def test_lazy_evaluation(self):
        """_iter_item should be lazy (generator, not list)"""
        gen = _iter_item([1, 2, 3])
        assert hasattr(gen, '__next__')
        assert hasattr(gen, '__iter__')
        assert iter(gen) is gen