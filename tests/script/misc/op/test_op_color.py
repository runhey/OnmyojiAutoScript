"""
Tests for script.misc.op.color

RGB is a tuple subclass with only as_int()/as_uint8(). Alasio has no reference
tests for it.
"""
import pytest

from script.misc.op import RGB


class TestRGBIsATuple:
    def test_tuple_behaviour(self):
        rgb = RGB((1, 2, 3))
        assert isinstance(rgb, tuple)
        assert tuple(rgb) == (1, 2, 3)
        assert rgb[0] == 1


class TestAsInt:
    def test_rounds_by_default(self):
        assert RGB((1.4, 2.6, 3.2)).as_int() == (1, 3, 3)

    def test_truncates_when_round_value_is_false(self):
        assert RGB((1.9, 2.9, 3.9)).as_int(round_value=False) == (1, 2, 3)

    def test_returns_an_rgb(self):
        assert isinstance(RGB((1.4, 2.6, 3.2)).as_int(), RGB)


class TestAsUint8:
    def test_clamps_above_255(self):
        assert RGB((300, 256, 255)).as_uint8() == (255, 255, 255)

    def test_clamps_below_0(self):
        assert RGB((-1, -20, 0)).as_uint8() == (0, 0, 0)

    def test_rounds_by_default(self):
        assert RGB((1.6, 2.4, 3.5)).as_uint8() == (2, 2, 4)

    def test_truncates_when_round_value_is_false(self):
        assert RGB((1.9, 2.9, 3.9)).as_uint8(round_value=False) == (1, 2, 3)

    def test_returns_an_rgb(self):
        assert isinstance(RGB((1, 2, 3)).as_uint8(), RGB)
