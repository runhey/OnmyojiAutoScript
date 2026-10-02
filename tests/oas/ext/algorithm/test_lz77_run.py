"""
Tests for oas.ext.algorithm.lz77.match_run().

``match_run(data, index, min_length=1, max_length=0)`` finds the longest run
of identical bytes starting from ``index`` in a memoryview of bytes.

Returns ``(run_byte, run_length)`` where ``run_byte`` is the integer byte
value (0-255) and ``run_length`` is at least ``min_length``.
"""

import pytest

from oas.ext.algorithm.lz77 import match_run

# ==============================================================================
# Helpers
# ==============================================================================

_mv = memoryview  # short alias for readability in parametrize tables

# ==============================================================================
# Basic run detection — default parameters
# ==============================================================================


class TestBasicRunDetection:
    """Run-finding with default ``min_length=1, max_length=0``."""

    @pytest.mark.parametrize("data, index, expected", [
        (_mv(b"aaaab"), 0, (97, 4)),   # run in middle of data
        (_mv(b"bbbaaa"), 3, (97, 3)),   # non-zero start index
        (_mv(b"aaaaaa"), 2, (97, 4)),   # start inside a run
        (_mv(b"ab"), 1, (98, 1)),   # last byte alone
        (_mv(b"xxxx"), 0, (120, 4)),  # entire data is one run
        (_mv(b"aaabaaa"), 0, (97, 3)),  # stops at first differing byte
        (_mv(b"z"), 0, (122, 1)),  # single element
        (_mv(b"zz"), 0, (122, 2)),  # two identical bytes
        (_mv(b"zx"), 0, (122, 1)),  # two different bytes
        (_mv(b"abbbb"), 1, (98, 4)),   # run extends to end
        (_mv(b"abc"), 0, (97, 1)),   # no run, length 1
        (_mv(b"abcdef"), 5, (102, 1)),  # last element
        (_mv(b"abcc"), 2, (99, 2)),   # second-to-last same as last
        (_mv(b"abcx"), 2, (99, 1)),   # second-to-last different from last
    ])
    def test_run(self, data, index, expected):
        """Parametrized run detection with default parameters."""
        result = match_run(data, index)
        assert result == expected


# ==============================================================================
# Byte value coverage
# ==============================================================================


class TestVariousByteValues:
    """Correct behaviour with different byte values (null, high, etc.)."""

    @pytest.mark.parametrize("data, expected", [
        (_mv(b"\x00\x00\x00\x01"), (0, 3)),
        (_mv(b"\xff\xff\xff\xfe"), (255, 3)),
        (_mv(b"\x7f\x7f\x7f\x80"), (127, 3)),
    ])
    def test_specific_values(self, data, expected):
        """Runs of null, high, and mid-range byte values."""
        assert match_run(data, 0) == expected

    def test_all_byte_values_solo(self):
        """Each byte value 0-255 as a single-element run (index 0, length 1)."""
        for bval in range(256):
            data = memoryview(bytes([bval]))
            assert match_run(data, 0) == (bval, 1), f"Failed for byte value {bval}"


# ==============================================================================
# min_length parameter
# ==============================================================================


class TestMinLength:
    """Behaviour of the ``min_length`` parameter."""

    @pytest.mark.parametrize("data, index, min_length, expected", [
        (_mv(b"abc"), 0, 1, (97, 1)),  # default-equivalent
        (_mv(b"aaaa"), 0, 2, (97, 4)),  # actual run > min
        (_mv(b"aabc"), 0, 2, (97, 2)),  # actual run == min
        (_mv(b"abc"), 0, 5, (97, 0)),  # actual run < min
        (_mv(b"ab"), 0, 1, (97, 1)),  # min=1 on a short run
        (_mv(b"ab"), 1, 10, (98, 0)),  # min larger than remaining data
        (_mv(b"abc"), 0, 0, (97, 1)),  # min=0
        (_mv(b"ab"), 0, 0, (97, 1)),  # min=0 on run of 1
        (_mv(b"zzzz"), 0, 2, (122, 4)),  # entire run with min satisfied
    ])
    def test_min_length(self, data, index, min_length, expected):
        """Parametrized min_length scenarios."""
        result = match_run(data, index, min_length=min_length)
        assert result == expected


# ==============================================================================
# max_length parameter
# ==============================================================================


class TestMaxLength:
    """Behaviour of the ``max_length`` parameter."""

    @pytest.mark.parametrize("data, index, max_length, expected", [
        # Default: 0 means no limit
        (_mv(b"aaaaab"), 0, 0, (97, 5)),

        # Basic capping
        (_mv(b"aaaaa"), 0, 3, (97, 3)),
        (_mv(b"aaaab"), 0, 3, (97, 3)),  # max equals actual run
        (_mv(b"aab"), 0, 10, (97, 2)),  # max larger than actual run

        # Boundary: max_length=1 (was a bug — now fixed)
        (_mv(b"aaaa"), 0, 1, (97, 1)),
        (_mv(b"a"), 0, 1, (97, 1)),
        (_mv(b"ab"), 0, 1, (97, 1)),

        # Stops early before differing byte
        (_mv(b"aaab"), 0, 2, (97, 2)),

        # Large data capping
        (_mv(b"a" * 10000), 0, 50, (97, 50)),
    ])
    def test_max_length(self, data, index, max_length, expected):
        """Parametrized max_length scenarios."""
        result = match_run(data, index, max_length=max_length)
        assert result == expected


# ==============================================================================
# Combined min_length and max_length
# ==============================================================================


class TestCombinedMinMaxLength:
    """Interaction between ``min_length`` and ``max_length``."""

    @pytest.mark.parametrize("data, index, min_length, max_length, expected", [
        # Both within range
        (_mv(b"aaaaa"), 0, 2, 10, (97, 5)),  # actual between min and max
        (_mv(b"aaaaaa"), 0, 3, 3, (97, 3)),  # min == max

        # Run shorter than min → length 0
        (_mv(b"abc"), 0, 5, 10, (97, 0)),  # run < min < max
        (_mv(b"abc"), 0, 5, 3, (97, 0)),  # min > max, match_len < min

        # Run capped by max
        (_mv(b"aaaaaaa"), 0, 2, 4, (97, 4)),  # min < max < actual

        # Actual run between min and max
        (_mv(b"aaaa"), 0, 2, 10, (97, 4)),  # min < actual < max
    ])
    def test_combined(self, data, index, min_length, max_length, expected):
        """Parametrized combined min_length + max_length scenarios."""
        result = match_run(data, index, min_length=min_length, max_length=max_length)
        assert result == expected


# ==============================================================================
# Large data stress tests
# ==============================================================================


class TestLargeData:
    """Correctness with large memoryviews."""

    @pytest.mark.parametrize("data, index, kwargs, expected", [
        (_mv(b"a" * 10000 + b"b"), 0, {}, (97, 10000)),
        (_mv(b"x" * 5000 + b"y" * 5000), 5000, {}, (121, 5000)),
        (_mv(b"a" * 10000), 0, {"max_length": 50}, (97, 50)),
        (_mv(b"a" * 10000), 0, {"min_length": 5000}, (97, 10000)),
    ])
    def test_large_data(self, data, index, kwargs, expected):
        """Various large-data scenarios."""
        result = match_run(data, index, **kwargs)
        assert result == expected

    def test_alternating_long_data(self):
        """Long data where no two consecutive bytes are the same -> run length 1."""
        data = memoryview(bytes([i % 256 for i in range(10000)]))
        assert match_run(data, 0) == (0, 1)


# ==============================================================================
# Memoryview input types
# ==============================================================================


class TestMemoryviewInput:
    """Correct handling of different memoryview sources."""

    @pytest.mark.parametrize("data, expected", [
        (_mv(b"aaa"), (97, 3)),
        (_mv(bytearray(b"bbb")), (98, 3)),
        (_mv(b"cccddd")[3:], (100, 3)),
    ])
    def test_input_types(self, data, expected):
        """memoryview from bytes, bytearray, and sliced."""
        assert match_run(data, 0) == expected


# ==============================================================================
# Index out of bounds
# ==============================================================================


class TestIndexError:
    """``IndexError`` is raised when the start index is out of bounds."""

    @pytest.mark.parametrize("data, index", [
        # Empty data — any index is out of range
        (_mv(b""), 0),
        (_mv(b""), 1),
        (_mv(b""), -1),

        # Positive index beyond the last element
        (_mv(b"abc"), 3),
        (_mv(b"abc"), 5),
        (_mv(b"abc"), 100),

        # Negative index beyond the first element
        (_mv(b"abc"), -4),
        (_mv(b"abc"), -10),

        # One-element data, index past it
        (_mv(b"z"), 1),
        (_mv(b"z"), 2),

        # Large data, index past the end
        (_mv(b"a" * 1000), 1000),
        (_mv(b"a" * 1000), 2000),
    ])
    def test_index_out_of_bounds(self, data, index):
        """All out-of-bounds indices must raise IndexError."""
        with pytest.raises(IndexError):
            match_run(data, index)

    @pytest.mark.parametrize("data, index", [
        # Negative indices that *are* valid in Python
        (_mv(b"abc"), -1),
        (_mv(b"abc"), -2),
        (_mv(b"abc"), -3),
        (_mv(b"z"), -1),
        (_mv(b"abcd"), -4),
    ])
    def test_negative_index_in_bounds(self, data, index):
        """Negative indices that resolve to a valid position must NOT raise."""
        result = match_run(data, index)
        assert isinstance(result, tuple)
        assert len(result) == 2


# ==============================================================================
# Regression tests
# ==============================================================================


class TestRegression:
    """Regression tests for specific bugs or edge conditions."""

    def test_no_match_returns_zero(self):
        """No match (min_length > remaining data) returns length 0."""
        # Single byte with min_length > 1 — only possible run is too short
        assert match_run(memoryview(b"z"), 0, min_length=10) == (122, 0)
        # Two different bytes — actual run is 1, min_length requires more
        assert match_run(memoryview(b"ab"), 0, min_length=5) == (97, 0)
        # Entire data is one run but min_length exceeds data length
        assert match_run(memoryview(b"aaaa"), 0, min_length=10) == (97, 0)

    def test_matched_length_less_than_min_length(self):
        """Actual run shorter than min_length returns length 0."""
        # Run of 2 at start (b"aa"bc), min_length=3
        assert match_run(memoryview(b"aabc"), 0, min_length=3) == (97, 0)
        # Run of 3 at start (b"aaa"bc), min_length=5
        assert match_run(memoryview(b"aaabc"), 0, min_length=5) == (97, 0)
        # Run of 1 at non-zero index (b"ab"c), min_length=2
        assert match_run(memoryview(b"abc"), 2, min_length=2) == (99, 0)

    def test_min_length_returns_correct_byte_value(self):
        """Byte value is preserved even when length is 0."""
        result = match_run(memoryview(b"ab"), 0, min_length=5)
        assert result == (97, 0)

    def test_max_length_does_not_affect_byte_value(self):
        """max_length truncation does not corrupt the returned byte value."""
        result = match_run(memoryview(b"\xff\xff\xff\xff"), 0, max_length=2)
        assert result == (255, 2)
