"""
Tests for script.misc.op.slist

Slist is a list proxy that can behave like a small in-memory table. Alasio only
uses it in alasio/assets_dev/parse.py and OAS currently has no caller, so these
tests exist only to pin the API. Alasio has no reference tests for it.
"""
import pytest

from script.misc.op import Slist


class Row:
    def __init__(self, domain, route, value=0):
        self.domain = domain
        self.route = route
        self.value = value

    def __repr__(self):
        return f'Row({self.domain!r}, {self.route!r})'

    def bump(self, by=1):
        self.value += by
        return self.value


@pytest.fixture
def rows():
    return [
        Row('Combat', 'A', 1),
        Row('Combat', 'B', 2),
        Row('Daily', 'A', 3),
    ]


class TestListLike:
    def test_iteration(self, rows):
        assert list(Slist(rows)) == rows

    def test_len_and_count(self, rows):
        slist = Slist(rows)
        assert len(slist) == 3
        assert slist.count == 3

    def test_bool(self):
        assert bool(Slist([1])) is True
        assert bool(Slist([])) is False

    def test_int_index(self, rows):
        assert Slist(rows)[1] is rows[1]

    def test_slice_returns_slist(self, rows):
        sliced = Slist(rows)[1:]
        assert isinstance(sliced, Slist)
        assert len(sliced) == 2

    def test_contains(self, rows):
        slist = Slist(rows)
        assert rows[0] in slist
        assert Row('None', 'None') not in slist

    def test_str_looks_like_a_list(self):
        assert str(Slist([1, 2, 3])) == '[1, 2, 3]'


class TestSelect:
    def test_select_by_attribute(self, rows):
        selected = Slist(rows).select(domain='Combat')
        assert isinstance(selected, Slist)
        assert [r.route for r in selected] == ['A', 'B']

    def test_select_multiple_attributes(self, rows):
        assert [r.route for r in Slist(rows).select(domain='Combat', route='B')] == ['B']

    def test_select_no_match(self, rows):
        assert len(Slist(rows).select(domain='Nope')) == 0


class TestIndex:
    def test_index_select(self, rows):
        slist = Slist(rows)
        slist.index_create('domain', 'route')
        assert [r.value for r in slist.index_select('Combat', 'A')] == [1]

    def test_index_select_missing_returns_empty(self, rows):
        slist = Slist(rows)
        slist.index_create('domain')
        assert len(slist.index_select('Nope')) == 0


class TestTransform:
    def test_filter(self, rows):
        assert [r.route for r in Slist(rows).filter(lambda r: r.value >= 2)] == ['B', 'A']

    def test_get(self, rows):
        assert Slist(rows).get('route') == ['A', 'B', 'A']

    def test_set(self, rows):
        Slist(rows).set(value=9)
        assert [r.value for r in rows] == [9, 9, 9]

    def test_call(self, rows):
        assert Slist(rows).call('bump', by=10) == [11, 12, 13]


class TestFirstOrNone:
    def test_returns_the_first_item(self, rows):
        assert Slist(rows).first_or_none() is rows[0]

    def test_empty_returns_none(self):
        assert Slist([]).first_or_none() is None


class TestReturnsNewSlist:
    def test_add_scalar(self):
        assert list(Slist([1, 2]).add(3)) == [1, 2, 3]

    def test_add_list(self):
        assert list(Slist([1, 2]).add([3, 4])) == [1, 2, 3, 4]

    def test_add_slist(self):
        assert list(Slist([1, 2]).add(Slist([3, 4]))) == [1, 2, 3, 4]

    def test_add_returns_a_new_slist(self):
        base = Slist([1])
        assert base.add(2) is not base

    def test_remove_scalar(self):
        assert list(Slist([1, 2, 2]).remove(2)) == [1]

    def test_remove_list(self):
        assert list(Slist([1, 2, 3]).remove([1, 3])) == [2]

    def test_remove_slist(self):
        assert list(Slist([1, 2, 3]).remove(Slist([2]))) == [1, 3]

    def test_sort_by_attribute(self, rows):
        assert [r.route for r in Slist(rows).sort('route')] == ['A', 'A', 'B']

    def test_sort_without_attributes_returns_self(self, rows):
        slist = Slist(rows)
        assert slist.sort() is slist

    def test_sort_empty_returns_self(self):
        slist = Slist([])
        assert slist.sort('anything') is slist
