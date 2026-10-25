import pytest

from oas.ext.algorithm.const import MAX_INT64
from oas.ext.algorithm.vint import decode_vint, decode_vint_list, encode_vint, encode_vint_list


class TestDecodeVint:
    """Tests for decode_vint()"""

    @pytest.mark.parametrize("data, expected_val, expected_read", [
        # Single byte values
        (b'\x00', 0, 1),
        (b'\x7f', 127, 1),
        # Boundary: 128 and 129 require a second byte
        (b'\x80\x00', 128, 2),
        (b'\x80\x01', 129, 2),
        # Borrow case: 16384 = 128*128 -> 0xff, 0x00
        (b'\xff\x00', 16384, 2),
        (b'\xff\x01', 16385, 2),
        # Three-byte values
        (b'\x80\x80\x00', 16512, 3),
        (b'\x80\x80\x01', 16513, 3),
    ])
    def test_decode_values(self, data, expected_val, expected_read):
        """Parametrized decode test covering single-byte, boundary, borrow and multi-byte values."""
        val, read = decode_vint(data)
        assert val == expected_val
        assert read == expected_read

    def test_decode_bytearray_input(self):
        """decode_vint should accept bytearray as well as bytes."""
        val, read = decode_vint(bytearray(b'\x80\x00'))
        assert val == 128
        assert read == 2

    def test_decode_partial_read(self):
        """If longer data is passed, only the bytes needed are consumed."""
        val, read = decode_vint(b'\x80\x01\xff\xff\xff')
        assert val == 129
        assert read == 2

    @pytest.mark.parametrize("data", [
        b'\xff' * 8 + b'\x00',  # 8 high bytes, max value exceeds INT64
        b'\x80' * 9 + b'\x00',  # 9 high bytes, min value exceeds INT64
        b'\xff' * 100,          # long stream of high bytes
    ])
    def test_decode_exceeds_int64_raises(self, data):
        """decode_vint should raise ValueError when the value exceeds INT64."""
        with pytest.raises(ValueError):
            decode_vint(data)

    def test_decode_near_int64_boundary(self):
        """9-byte values that stay within INT64 must still decode."""
        val, read = decode_vint(b'\x80' * 8 + b'\x00')
        assert val == 72624976668147840
        assert read == 9

    def test_decode_max_int64(self):
        """Decode the encoding of MAX_INT64 itself."""
        encoded = encode_vint(MAX_INT64)
        val, read = decode_vint(encoded)
        assert val == MAX_INT64
        assert read == len(encoded)

    @pytest.mark.parametrize("data", [
        b'\x80',        # one high byte, no terminating byte
        b'\x80\x80',    # two high bytes
        b'\xff',        # high byte with the max payload
        b'\x80' * 8,  # 8 high bytes, value would stay within INT64
        b'\xff\xff\xff',  # three high bytes
    ])
    def test_decode_truncated_raises(self, data):
        """decode_vint should raise ValueError when the stream ends inside a vint."""
        with pytest.raises(ValueError):
            decode_vint(data)

    def test_decode_empty_data_raises(self):
        """decode_vint should raise ValueError on empty data: calling the function implies data is expected."""
        with pytest.raises(ValueError):
            decode_vint(b'')


class TestEncodeVint:
    """Tests for encode_vint()"""

    @pytest.mark.parametrize("num, expected", [
        (0, b'\x00'),
        (127, b'\x7f'),
        (128, b'\x80\x00'),
        (129, b'\x80\x01'),
        # Borrow case: 16384 = 128*128 -> 0xff, 0x00
        (16384, b'\xff\x00'),
        (16385, b'\xff\x01'),
        # Three-byte values
        (16512, b'\x80\x80\x00'),
        (16513, b'\x80\x80\x01'),
        # Larger values
        (500000, b'\x9d\xc1\x20'),
        (1048576, b'\xbe\xff\x00'),   # 2^20
        (16777216, b'\x86\xfe\xff\x00'),  # 2^24
    ])
    def test_encode_values(self, num, expected):
        """Parametrized encode test covering single-byte, boundary, borrow and large values."""
        assert encode_vint(num) == expected

    @pytest.mark.parametrize("negative", [-1, -128, -129, -16384, -100000])
    def test_encode_negative_raises(self, negative):
        """encode_vint should raise ValueError on negative input."""
        with pytest.raises(ValueError):
            encode_vint(negative)

    @pytest.mark.parametrize("num", [MAX_INT64 + 1, MAX_INT64 * 2, 1 << 70])
    def test_encode_exceeds_int64_raises(self, num):
        """encode_vint should raise ValueError on values exceeding INT64."""
        with pytest.raises(ValueError):
            encode_vint(num)

    def test_encode_max_int64(self):
        """encode_vint should accept MAX_INT64 itself."""
        encoded = encode_vint(MAX_INT64)
        assert isinstance(encoded, bytes)
        decoded, read = decode_vint(encoded)
        assert decoded == MAX_INT64
        assert read == len(encoded)


class TestVintRoundTrip:
    """Round-trip tests: encode then decode must return the original value."""

    @pytest.mark.parametrize("value", [
        0, 1, 5, 10,
        126, 127, 128, 129, 130,
        255, 256, 257,
        16383, 16384, 16385, 16386,
        16512, 16513,
        20000, 100000, 500000,
        1048576,    # 2^20
        16777215,   # 2^24 - 1
        16777216,   # 2^24
    ])
    def test_round_trip(self, value):
        encoded = encode_vint(value)
        decoded, read = decode_vint(encoded)
        assert decoded == value
        assert read == len(encoded)

    def test_round_trip_boundary_127_128_129(self):
        """Explicitly verify the 126-130 boundary range."""
        for v in range(126, 131):
            encoded = encode_vint(v)
            decoded, read = decode_vint(encoded)
            assert decoded == v
            assert read == len(encoded)

    @pytest.mark.parametrize("value", range(0, 500))
    def test_round_trip_many_values(self, value):
        """Round-trip for 0..499 to catch off-by-one errors."""
        encoded = encode_vint(value)
        decoded, read = decode_vint(encoded)
        assert decoded == value
        assert read == len(encoded)

    @pytest.mark.parametrize("shift, offset", [
        (s, o) for s in range(7, 25) for o in (-2, -1, 0, 1, 2)
    ])
    def test_round_trip_powers_of_two(self, shift, offset):
        """Round-trip for values near powers of two (2^7 .. 2^24 +/- 2)."""
        v = (1 << shift) + offset
        if v < 0:
            pytest.skip("Negative offset makes value negative")
        encoded = encode_vint(v)
        decoded, read = decode_vint(encoded)
        assert decoded == v, f"Round-trip failed for {v} (2^{shift} + {offset})"
        assert read == len(encoded)


class TestEncodeVintList:
    """Tests for encode_vint_list()"""

    @pytest.mark.parametrize("nums, expected", [
        ([0], b'\x00'),
        ([0, 0], b'\x00\x00'),
        ([127, 128], b'\x7f\x80\x00'),
        ([128, 129], b'\x80\x00\x80\x01'),
        ([16384, 0], b'\xff\x00\x00'),
        ([1, 2, 3], b'\x01\x02\x03'),
        ([], b''),
    ])
    def test_encode_values(self, nums, expected):
        """Parametrized encode test covering single, multiple, and edge cases."""
        assert encode_vint_list(nums) == expected

    @pytest.mark.parametrize("nums", [
        [0, 1, 5, 10],
        [126, 127, 128, 129, 130],
        [16383, 16384, 16385],
        [16512, 16513],
        [500000, 1048576, 16777216],
    ])
    def test_encode_always_returns_bytes(self, nums):
        """encode_vint_list should always return bytes."""
        result = encode_vint_list(nums)
        assert isinstance(result, bytes)

    def test_large_list(self):
        """Encode a large list of values and verify length grows reasonably."""
        nums = list(range(100))
        result = encode_vint_list(nums)
        # Each value 0-99 encodes as single byte, so length should be 100
        assert len(result) == 100

    @pytest.mark.parametrize("nums", [
        [-1],
        [0, -5],
        [MAX_INT64 + 1],
        [10, 1 << 70],
    ])
    def test_encode_invalid_raises(self, nums):
        """encode_vint_list should raise ValueError on negative or oversized integers."""
        with pytest.raises(ValueError):
            encode_vint_list(nums)


class TestDecodeVintList:
    """Tests for decode_vint_list()"""

    @pytest.mark.parametrize("data, total, expected", [
        (b'\x00', 1, [0]),
        (b'\x00\x00', 2, [0, 0]),
        (b'\x7f\x80\x00', 2, [127, 128]),
        (b'\x80\x00\x80\x01', 2, [128, 129]),
        (b'\xff\x00\x00', 2, [16384, 0]),
        (b'\x01\x02\x03', 3, [1, 2, 3]),
    ])
    def test_decode_values(self, data, total, expected):
        """Parametrized decode test for vint list."""
        result, _ = decode_vint_list(data, total)
        assert result == expected

    def test_decode_bytearray_input(self):
        """decode_vint_list should accept bytearray as well as bytes."""
        result, _ = decode_vint_list(bytearray(b'\x80\x00\x80\x01'), 2)
        assert result == [128, 129]

    def test_decode_extra_trailing_data(self):
        """Trailing bytes beyond total count should be ignored."""
        # \x80\x01 is 129, the trailing \xff\xff is ignored
        result, _ = decode_vint_list(b'\x80\x01\xff\xff\xff', 1)
        assert result == [129]

    def test_total_exceeds_available_data(self):
        """If total exceeds available data, only available integers are decoded."""
        result, _ = decode_vint_list(b'\x80\x01', 5)
        assert result == [129]

    @pytest.mark.parametrize("total", [1, 3])
    def test_decode_empty_data_raises(self, total):
        """decode_vint_list should raise ValueError on empty data: calling
        the function implies data is expected."""
        with pytest.raises(ValueError):
            decode_vint_list(b'', total)

    @pytest.mark.parametrize("total", [0, -1, -128, -100000])
    def test_decode_non_positive_total_raises(self, total):
        """decode_vint_list should raise ValueError when total is not positive."""
        with pytest.raises(ValueError):
            decode_vint_list(b'\x00', total)

    @pytest.mark.parametrize("data", [
        b'\xff' * 8 + b'\x00',  # 8 high bytes, max value exceeds INT64
        b'\x80' * 9 + b'\x00',  # 9 high bytes, min value exceeds INT64
        b'\xff' * 100,          # long stream of high bytes
    ])
    def test_decode_exceeds_int64_raises(self, data):
        """decode_vint_list should raise ValueError when the value exceeds INT64."""
        with pytest.raises(ValueError):
            decode_vint_list(data, 1)

    def test_decode_near_int64_boundary(self):
        """9-byte values that stay within INT64 must still decode."""
        result, total_read = decode_vint_list(b'\x80' * 8 + b'\x00', 1)
        assert result == [72624976668147840]
        assert total_read == 9

    def test_decode_max_int64(self):
        """Decode the encoding of MAX_INT64 itself."""
        encoded = encode_vint_list([MAX_INT64])
        result, total_read = decode_vint_list(encoded, 1)
        assert result == [MAX_INT64]
        assert total_read == len(encoded)

    def test_decode_returns_total_read(self):
        """Total read should count bytes consumed, including multi-byte numbers."""
        result, total_read = decode_vint_list(b'\x7f\x80\x00', 2)
        assert result == [127, 128]
        assert total_read == 3

    def test_decode_total_read_with_trailing_data(self):
        """Total read should not count bytes beyond the requested numbers."""
        result, total_read = decode_vint_list(b'\x80\x01\xff\xff\xff', 1)
        assert result == [129]
        assert total_read == 2

    @pytest.mark.parametrize("data, total", [
        (b'\x80', 1),            # one high byte, no terminating byte
        (b'\x80\x80', 1),        # two high bytes
        (b'\xff', 1),            # high byte with the max payload
        (b'\x00\x80', 2),        # complete vint followed by a truncated one
        (b'\x80\x01\x80', 3),    # complete vint followed by a truncated one
    ])
    def test_decode_truncated_raises(self, data, total):
        """decode_vint_list should raise ValueError when the stream ends inside a vint."""
        with pytest.raises(ValueError):
            decode_vint_list(data, total)


class TestVintListRoundTrip:
    """Round-trip tests for encode_vint_list / decode_vint_list."""

    @pytest.mark.parametrize("nums", [
        [0],
        [0, 1, 2, 3],
        [127, 128, 129],
        [16383, 16384, 16385],
        [16512, 16513, 16514],
        [500000, 1048576, 16777216],
        list(range(100)),
    ])
    def test_round_trip(self, nums):
        """Encode then decode must return the original list."""
        encoded = encode_vint_list(nums)
        result, _ = decode_vint_list(encoded, len(nums))
        assert result == nums

    @pytest.mark.parametrize("nums", [
        [10, 20, 30],
        [128, 256, 512],
        [1000, 10000, 100000],
    ])
    def test_round_trip_subset_decode(self, nums):
        """Decode only first N elements of an encoded list."""
        encoded = encode_vint_list(nums)
        result, _ = decode_vint_list(encoded, 2)
        assert result == nums[:2]

    def test_round_trip_concatenation(self):
        """Concatenating two encoded lists should decode as a single list."""
        list_a = [10, 20]
        list_b = [30, 40]
        encoded = encode_vint_list(list_a) + encode_vint_list(list_b)
        result, _ = decode_vint_list(encoded, 4)
        assert result == [10, 20, 30, 40]

    def test_round_trip_max_int64(self):
        """Round-trip the INT64 boundary value through the list API."""
        encoded = encode_vint_list([0, MAX_INT64])
        result, total_read = decode_vint_list(encoded, 2)
        assert result == [0, MAX_INT64]
        assert total_read == len(encoded)
