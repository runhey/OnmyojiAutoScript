"""
Tests for script.misc.op.rng

Alasio has no reference tests for alasio/base/op. The behaviour pinned here is
Alasio's, which differs from the copy in oas/base/utils/utils.py: random.randint
is a closed interval [a, b] and a/b are rounded before drawing.
"""
import random

import pytest

from script.misc.op import (
    random_friendly_id,
    random_id,
    random_normal_distribution_int,
    random_rectangle_point,
)


class TestRandomNormalDistributionInt:
    def test_returns_b_when_a_is_not_smaller(self):
        assert random_normal_distribution_int(7, 3) == 3
        assert random_normal_distribution_int(5, 5) == 5

    def test_rounds_the_bounds_first(self, monkeypatch):
        # round(1.4) == 1, round(5.6) == 6 -> interval [1, 6]
        seen = []

        def fake_randint(a, b):
            seen.append((a, b))
            return a

        monkeypatch.setattr(random, "randint", fake_randint)
        random_normal_distribution_int(1.4, 5.6)
        assert seen == [(1, 6)] * 3

    def test_draws_from_the_closed_interval(self, monkeypatch):
        seen = []

        def fake_randint(a, b):
            seen.append((a, b))
            return b

        monkeypatch.setattr(random, "randint", fake_randint)
        assert random_normal_distribution_int(1, 5) == 5
        assert seen == [(1, 5)] * 3

    def test_upper_bound_is_reachable(self):
        # OAS's np.random.randint(a, b) is half-open and would never return b
        random.seed(1234)
        values = {random_normal_distribution_int(0, 1) for _ in range(300)}
        assert values == {0, 1}

    def test_n_controls_the_number_of_draws(self, monkeypatch):
        seen = []
        monkeypatch.setattr(random, "randint", lambda a, b: seen.append(1) or b)
        random_normal_distribution_int(1, 9, n=7)
        assert len(seen) == 7

    def test_result_is_an_int(self):
        assert isinstance(random_normal_distribution_int(1, 9), int)


class TestRandomRectanglePoint:
    def test_point_stays_inside_the_area(self):
        random.seed(0)
        for _ in range(200):
            x, y = random_rectangle_point((10, 20, 30, 40))
            assert 10 <= x <= 30
            assert 20 <= y <= 40

    def test_returns_a_tuple_of_two(self):
        point = random_rectangle_point((0, 0, 5, 5))
        assert isinstance(point, tuple)
        assert len(point) == 2

    def test_uses_closed_bounds(self, monkeypatch):
        # every draw returns the bottom-right corner
        monkeypatch.setattr(random, "randint", lambda a, b: b)
        assert random_rectangle_point((10, 20, 30, 40)) == (30, 40)


class TestRandomId:
    def test_default_length(self):
        assert len(random_id()) == 6

    def test_custom_length(self):
        assert len(random_id(20)) == 20

    def test_base62_charset(self):
        charset = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
        assert set(random_id(200)) <= charset


class TestRandomFriendlyId:
    def test_default_length(self):
        assert len(random_friendly_id()) == 10

    def test_custom_length(self):
        assert len(random_friendly_id(25)) == 25

    def test_excludes_confusable_characters(self):
        confusable = set('0oO1iIl5Ss2ZzD8BuUvVwWxX')
        assert set(random_friendly_id(500)).isdisjoint(confusable)
