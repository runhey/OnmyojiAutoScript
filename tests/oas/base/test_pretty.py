"""
Tests for oas.base.pretty

Alasio has no tests/base/test_pretty.py. Only pretty_time is covered here, moved
from tests/oas/ext/test_perf.py now that it lives in oas.base.pretty.
"""
import pytest

from oas.base.pretty import pretty_time


class TestPrettyTime:
    @pytest.mark.parametrize(
        'second, expected',
        [
            (1, '1.000s'),
            (1.5, '1.500s'),
            (2, '2.000s'),
            (60, '60.000s'),
            (0.001, '1.000ms'),
            (0.0015, '1.500ms'),
            (0.5, '500.000ms'),
            (0.9999, '999.900ms'),
        ],
    )
    def test_seconds_and_milliseconds(self, second, expected):
        assert pretty_time(second) == expected

    @pytest.mark.parametrize(
        'second, expected',
        [
            (0.001, '1.000ms'),
            (0.000999, '999.000us'),
            (0.0001, '100.000us'),
            (1e-9, '0.001us'),
            (0, '0.000us'),
        ],
    )
    def test_microseconds_below_one_millisecond(self, second, expected):
        assert pretty_time(second) == expected

    def test_boundaries_are_inclusive_on_the_larger_unit(self):
        assert pretty_time(1).endswith('s')
        assert not pretty_time(1).endswith('ms')
        assert pretty_time(0.001).endswith('ms')
        assert not pretty_time(0.001).endswith('us')

    def test_always_three_decimal_places(self):
        for value in (0, 1e-9, 0.000123, 0.5, 1, 123.456):
            tail = pretty_time(value).rstrip('smu')
            assert len(tail.split('.')[1]) == 3
