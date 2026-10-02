import pytest

from oas.ext.algorithm.diffcooding import decode_diff, encode_diff


class TestEncodeDiff:
    """Tests for encode_diff."""

    def test_empty_list(self):
        """Empty list should return empty list."""
        assert encode_diff([]) == []

    def test_single_element(self):
        """Single element should encode to [element] (prev=0)."""
        assert encode_diff([42]) == [42]
        assert encode_diff([0]) == [0]
        assert encode_diff([-7]) == [-7]

    def test_positive_values(self):
        """Basic positive integer sequence."""
        result = encode_diff([10, 15, 13, 20, 25])
        assert result == [10, 5, -2, 7, 5]
        assert len(result) == 5

    def test_negative_values(self):
        """Sequence with negative values."""
        result = encode_diff([0, -5, -3, 10, 0])
        assert result == [0, -5, 2, 13, -10]

    def test_all_negative(self):
        """All negative values."""
        result = encode_diff([-10, -20, -15, -30])
        assert result == [-10, -10, 5, -15]

    def test_identical_values(self):
        """All identical values should produce first, then zeros."""
        result = encode_diff([5, 5, 5, 5])
        assert result == [5, 0, 0, 0]

    def test_zeros(self):
        """All zeros."""
        result = encode_diff([0, 0, 0])
        assert result == [0, 0, 0]

    def test_increasing_sequence(self):
        """Strictly increasing values — all deltas positive."""
        result = encode_diff([1, 3, 6, 10, 15])
        assert result == [1, 2, 3, 4, 5]

    def test_decreasing_sequence(self):
        """Strictly decreasing values — all deltas negative."""
        result = encode_diff([15, 10, 6, 3, 1])
        assert result == [15, -5, -4, -3, -2]

    def test_large_values(self):
        """Values near int32 boundary should round-trip correctly."""
        original = [2**31 - 1, -(2**31), 0, 2**31 - 1]
        result = encode_diff(original)
        # 2147483647 - 0, -2147483648 - 2147483647, 0 - (-2147483648), 2147483647 - 0
        assert result == [2147483647, -4294967295, 2147483648, 2147483647]

    def test_first_is_delta_from_zero(self):
        """First encoded element equals the first input element (prev=0)."""
        assert encode_diff([100]) == [100]
        assert encode_diff([-50]) == [-50]
        result = encode_diff([7, 14, 21])
        assert result[0] == 7

    def test_preserves_length(self):
        """Output length always matches input length."""
        for length in range(0, 10):
            data = list(range(length))
            assert len(encode_diff(data)) == length


class TestDecodeDiff:
    """Tests for decode_diff."""

    def test_empty_list(self):
        """Empty list should return empty list."""
        assert decode_diff([]) == []

    def test_single_element(self):
        """Single element should decode to the same value (prev=0)."""
        assert decode_diff([42]) == [42]
        assert decode_diff([0]) == [0]
        assert decode_diff([-7]) == [-7]

    def test_positive_deltas(self):
        """All positive deltas produce an increasing sequence."""
        result = decode_diff([10, 5, -2, 7, 5])
        assert result == [10, 15, 13, 20, 25]

    def test_negative_deltas(self):
        """Deltas with negative values."""
        result = decode_diff([0, -5, 2, 13, -10])
        assert result == [0, -5, -3, 10, 0]

    def test_all_zeros(self):
        """All zero deltas produce flat sequence."""
        result = decode_diff([5, 0, 0, 0])
        assert result == [5, 5, 5, 5]

    def test_single_zero_first(self):
        """First element zero, all deltas zero."""
        result = decode_diff([0, 0, 0])
        assert result == [0, 0, 0]

    def test_large_values(self):
        """Large deltas should decode correctly."""
        result = decode_diff([2147483647, -4294967295, 2147483648, 2147483647])
        # 0+2147483647, 2147483647+(-4294967295), -2147483648+2147483648, 0+2147483647
        assert result == [2147483647, -2147483648, 0, 2147483647]

    def test_preserves_length(self):
        """Output length always matches input length."""
        for length in range(0, 10):
            data = list(range(length))
            assert len(decode_diff(data)) == length


class TestDiffCodingRoundtrip:
    """Round-trip property tests: decode_diff(encode_diff(x)) == x."""

    ROUNDTRIP_CASES = [
        [],
        [0],
        [42],
        [-7],
        [10, 15, 13, 20, 25],
        [0, -5, -3, 10, 0],
        [-10, -20, -15, -30],
        [5, 5, 5, 5],
        [0, 0, 0],
        [1, 3, 6, 10, 15],
        [15, 10, 6, 3, 1],
        [2**31 - 1, -(2**31), 0, 2**31 - 1],
        [-2**63, 0, 2**63 - 1],
        [1],
        [1, 2],
        [1000000, 1000005, 999990, 1000010],
        [-1, -2, -3, -4, -5],
        [0, 1, 0, 1, 0, 1],
        [10],
        [10, 9, 8, 7, 6],
    ]

    @pytest.mark.parametrize("data", ROUNDTRIP_CASES)
    def test_roundtrip(self, data):
        """decode_diff(encode_diff(data)) should return the original data."""
        encoded = encode_diff(data)
        decoded = decode_diff(encoded)
        assert decoded == data

    def test_deterministic(self):
        """Encoding the same input twice produces identical output."""
        data = [10, 15, 13, 20, 25]
        assert encode_diff(data) == encode_diff(data)
        assert decode_diff(encode_diff(data)) == decode_diff(encode_diff(data))

    def test_identity_for_single(self):
        """For single-element lists, encode and decode are identity on the value."""
        for val in [0, 1, -1, 100, -100, 2**31 - 1]:
            assert decode_diff(encode_diff([val])) == [val]

    def test_large_random_roundtrip(self):
        """Large random sequence round-trips correctly."""
        data = [i * 7 % 113 - 50 for i in range(1000)]
        encoded = encode_diff(data)
        assert len(encoded) == 1000
        decoded = decode_diff(encoded)
        assert decoded == data
