import pytest

from oas.ext.algorithm.zigzag import decode_zigzag, decode_zigzag_iter, encode_zigzag, encode_zigzag_iter


class TestEncodeZigzag:
    """Tests for encode_zigzag() and encode_zigzag_iter()"""

    @pytest.mark.parametrize("data, expected", [
        ([0], [0]),
        ([-1], [1]),
        ([1], [2]),
        ([-2], [3]),
        ([2], [4]),
        ([-3], [5]),
        ([3], [6]),
        ([-4], [7]),
        ([4], [8]),
        ([-5], [9]),
        ([5], [10]),
    ])
    def test_single_values(self, data, expected):
        """Parametrized encode test for single values covering the formula."""
        assert encode_zigzag(data) == expected

    @pytest.mark.parametrize("data, expected", [
        ([0, 0, 0], [0, 0, 0]),
        ([1, -1, 2, -2], [2, 1, 4, 3]),
        ([-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5],
         [9, 7, 5, 3, 1, 0, 2, 4, 6, 8, 10]),
        ([], []),
    ])
    def test_multiple_values(self, data, expected):
        """Encode multiple values including zero and negative numbers."""
        assert encode_zigzag(data) == expected

    @pytest.mark.parametrize("data, expected", [
        ([0], [0]),
        ([-1], [1]),
        ([1], [2]),
        ([-2], [3]),
        ([2], [4]),
    ])
    def test_iter_single_values(self, data, expected):
        """encode_zigzag_iter yields same results as encode_zigzag for single values."""
        assert list(encode_zigzag_iter(data)) == expected

    def test_iter_multiple_values(self):
        """encode_zigzag_iter yields same results as encode_zigzag for multiple values."""
        data = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]
        assert list(encode_zigzag_iter(data)) == encode_zigzag(data)

    def test_iter_is_generator(self):
        """encode_zigzag_iter should return a generator (not a list)."""
        result = encode_zigzag_iter([1, 2, 3])
        import types
        assert isinstance(result, types.GeneratorType)

    def test_large_values(self):
        """Encode large positive and negative integers."""
        data = [1000000, -1000000, 2147483647, -2147483648]
        result = encode_zigzag(data)
        assert result == [2000000, 1999999, 4294967294, 4294967295]

    def test_empty_input(self):
        """Empty input returns empty list."""
        assert encode_zigzag([]) == []


class TestDecodeZigzag:
    """Tests for decode_zigzag() and decode_zigzag_iter()"""

    @pytest.mark.parametrize("data, expected", [
        ([0], [0]),
        ([1], [-1]),
        ([2], [1]),
        ([3], [-2]),
        ([4], [2]),
        ([5], [-3]),
        ([6], [3]),
        ([7], [-4]),
        ([8], [4]),
        ([9], [-5]),
        ([10], [5]),
    ])
    def test_single_values(self, data, expected):
        """Parametrized decode test for single values."""
        assert decode_zigzag(data) == expected

    @pytest.mark.parametrize("data, expected", [
        ([0, 0, 0], [0, 0, 0]),
        ([2, 1, 4, 3], [1, -1, 2, -2]),
        ([9, 7, 5, 3, 1, 0, 2, 4, 6, 8, 10],
         [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]),
        ([], []),
    ])
    def test_multiple_values(self, data, expected):
        """Decode multiple values."""
        assert decode_zigzag(data) == expected

    def test_iter_multiple_values(self):
        """decode_zigzag_iter yields same results as decode_zigzag."""
        data = [9, 7, 5, 3, 1, 0, 2, 4, 6, 8, 10]
        assert list(decode_zigzag_iter(data)) == decode_zigzag(data)

    def test_iter_is_generator(self):
        """decode_zigzag_iter should return a generator (not a list)."""
        result = decode_zigzag_iter([2, 4, 6])
        import types
        assert isinstance(result, types.GeneratorType)

    def test_large_values(self):
        """Decode large encoded values back to original integers."""
        data = [2000000, 1999999, 4294967294, 4294967295]
        result = decode_zigzag(data)
        assert result == [1000000, -1000000, 2147483647, -2147483648]

    def test_empty_input(self):
        """Empty input returns empty list."""
        assert decode_zigzag([]) == []


class TestZigzagRoundTrip:
    """Round-trip tests: encode then decode must return the original values."""

    @pytest.mark.parametrize("original", [
        [0],
        [1],
        [-1],
        [0, 0, 0],
        [1, -1, 2, -2],
        list(range(-10, 11)),
        list(range(0, 100)),
        list(range(-100, 0)),
        [1000000, -1000000, 2147483647, -2147483648],
        [],
    ])
    def test_round_trip(self, original):
        """Encoding then decoding yields the original data."""
        encoded = encode_zigzag(original)
        decoded = decode_zigzag(encoded)
        assert decoded == original

    @pytest.mark.parametrize("value", range(-50, 51))
    def test_round_trip_single_values(self, value):
        """Round-trip for every integer from -50 to 50."""
        encoded = encode_zigzag([value])
        decoded = decode_zigzag(encoded)
        assert decoded == [value]

    def test_round_trip_boundary_values(self):
        """Round-trip values around zero (±0, ±1, ±2)."""
        for v in range(-5, 6):
            encoded = encode_zigzag([v])
            decoded = decode_zigzag(encoded)
            assert decoded == [v]

    def test_round_trip_powers_of_two(self):
        """Round-trip for values that are powers of two and nearby offsets."""
        for shift in range(1, 16):
            for offset in (-2, -1, 0, 1, 2):
                v = (1 << shift) + offset
                encoded = encode_zigzag([v])
                decoded = decode_zigzag(encoded)
                assert decoded == [v], f"Round-trip failed for {v} (2^{shift} + {offset})"

    def test_round_trip_negative_powers_of_two(self):
        """Round-trip for negative values that are near powers of two."""
        for shift in range(1, 16):
            for offset in (-2, -1, 0, 1, 2):
                v = -((1 << shift) + offset)
                encoded = encode_zigzag([v])
                decoded = decode_zigzag(encoded)
                assert decoded == [v], f"Round-trip failed for {v} (-(2^{shift} + {offset}))"


class TestZigzagProperties:
    """Property-based invariants for zigzag encoding/decoding."""

    def test_encode_non_negative_is_even(self):
        """All non-negative inputs produce even outputs."""
        for i in range(0, 100):
            encoded = encode_zigzag([i])
            assert encoded[0] % 2 == 0, f"Expected even for {i}, got {encoded[0]}"

    def test_encode_negative_is_odd(self):
        """All negative inputs produce odd outputs."""
        for i in range(-100, 0):
            encoded = encode_zigzag([i])
            assert encoded[0] % 2 == 1, f"Expected odd for {i}, got {encoded[0]}"

    def test_decode_odd_is_negative(self):
        """All odd encoded values decode to negative numbers."""
        for encoded_val in [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]:
            decoded = decode_zigzag([encoded_val])
            assert decoded[0] < 0, f"Expected negative for {encoded_val}, got {decoded[0]}"

    def test_decode_even_is_non_negative(self):
        """All even encoded values decode to non-negative numbers."""
        for encoded_val in [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]:
            decoded = decode_zigzag([encoded_val])
            assert decoded[0] >= 0, f"Expected non-negative for {encoded_val}, got {decoded[0]}"

    def test_monotonic_positive(self):
        """Positive inputs produce strictly increasing even outputs."""
        encoded = encode_zigzag(list(range(0, 20)))
        for i in range(len(encoded) - 1):
            assert encoded[i] < encoded[i + 1], \
                f"Expected monotonic increasing, got {encoded[i]} >= {encoded[i + 1]}"

    def test_monotonic_negative(self):
        """Negative inputs (more negative first) produce decreasing odd outputs."""
        encoded = encode_zigzag(list(range(-20, 0)))
        for i in range(len(encoded) - 1):
            assert encoded[i] > encoded[i + 1], \
                f"Expected monotonic decreasing, got {encoded[i]} <= {encoded[i + 1]}"

    def test_abs_consistency(self):
        """abs(n) and n produce adjacent encoded values (even, odd)."""
        for n in range(1, 50):
            enc_pos = encode_zigzag([n])[0]    # even = 2*n
            enc_neg = encode_zigzag([-n])[0]   # odd  = 2*n - 1
            assert enc_pos == 2 * n
            assert enc_neg == 2 * n - 1

    def test_length_preserved(self):
        """Encoding preserves the length of the input list."""
        data = list(range(-50, 51))
        encoded = encode_zigzag(data)
        decoded = decode_zigzag(encoded)
        assert len(encoded) == len(data)
        assert len(decoded) == len(data)
