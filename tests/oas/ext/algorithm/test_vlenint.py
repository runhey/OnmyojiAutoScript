"""
Tests for ``oas.ext.algorithm.vlenint``.

``encode_vlenint`` encodes a list of integers (0 … 2³²-1) into a compact
variable-length binary format: per-value byte-lengths compressed with
``bit2coding`` (which carries its own vint count prefix, see
``encode_bit2``), and the values themselves packed little-endian.

The bit2 count prefix makes the encoding self-describing, ``decode_vlenint``
restores the original list without the caller passing the value count.

The imported building blocks (``encode_bit2``, ``decode_bit2``,
``pack_little_int``, ``unpack_little_int``) have their own comprehensive
coverage; this file tests the composition layer.
"""

import pytest

from oas.ext.algorithm.bit2coding import encode_bit2
from oas.ext.algorithm.vlenint import decode_vlenint, encode_vlenint, vlenint_value_check

# ==============================================================================
# vlenint_value_check — input validation
# ==============================================================================


class TestVlenintValueCheck:
    """``vlenint_value_check(data)`` — validation of input values."""

    def test_empty_passes(self):
        """Empty input should not raise."""
        vlenint_value_check([])

    def test_single_valid_value(self):
        """Single valid value should not raise."""
        vlenint_value_check([0])
        vlenint_value_check([1])
        vlenint_value_check([2 ** 32 - 1])

    def test_multiple_valid_values(self):
        """List of valid values should not raise."""
        vlenint_value_check([0, 1, 100, 40000, 2 ** 24])

    @pytest.mark.parametrize("bad", [
        [-1],
        [-1, 2, 3],
        [-100],
        [-2 ** 31],
    ])
    def test_negative_value_raises(self, bad):
        """Negative values should raise ValueError."""
        with pytest.raises(ValueError, match="Value must be >= 0"):
            vlenint_value_check(bad)

    @pytest.mark.parametrize("bad", [
        [2 ** 32],
        [2 ** 32 - 1, 2 ** 32],
        [2 ** 40],
    ])
    def test_overflow_raises(self, bad):
        """Values above 2**32 - 1 should raise ValueError."""
        with pytest.raises(ValueError, match="Value must be < 2\\*\\*32"):
            vlenint_value_check(bad)


# ==============================================================================
# encode_vlenint — basic structure and return type
# ==============================================================================


class TestEncodeVlenint:
    """``encode_vlenint(data) → bytes``."""

    def test_empty_encodes_count_zero(self):
        """Empty input produces the vint count prefix alone (count=0)."""
        assert encode_vlenint([]) == b'\x00'

    def test_returns_bytes(self):
        """Result is always bytes, not list[int] or generator."""
        result = encode_vlenint([1, 2, 3])
        assert isinstance(result, bytes)

    def test_negative_raises(self):
        """Negative values propagate from vlenint_value_check."""
        with pytest.raises(ValueError, match="Value must be >= 0"):
            encode_vlenint([-1])

    @pytest.mark.parametrize("data, description", [
        ([0], "single zero"),
        ([1], "single small positive"),
        ([255], "single uint8 max"),
        ([256], "single uint16 min"),
        ([2 ** 16 - 1], "single uint16 max"),
        ([2 ** 16], "single uint24 min"),
        ([2 ** 24 - 1], "single uint24 max"),
        ([2 ** 24], "single uint32 min"),
        ([2 ** 32 - 1], "single uint32 max"),
    ])
    def test_single_value(self, data, description):
        """Single values encode to some non-empty bytes."""
        result = encode_vlenint(data)
        assert len(result) >= 1

    def test_two_zeros(self):
        """Two zeros each take 0 value bytes, so only the prefix and the length section are present."""
        result = encode_vlenint([0, 0])
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_deterministic(self):
        """Same input produces identical bytes."""
        data = [0, 1, 255, 256, 65536, 2 ** 32 - 1]
        assert encode_vlenint(data) == encode_vlenint(data)


# ==============================================================================
# decode_vlenint — return type and basic structure
# ==============================================================================


class TestDecodeVlenint:
    """``decode_vlenint(data) → (list[int], int)``."""

    def test_empty_input_raises(self):
        """Empty data is not a valid encoding, the bit2 count prefix is missing."""
        with pytest.raises(ValueError, match="Data truncated"):
            decode_vlenint(b'')

    def test_decode_empty_list_encoding(self):
        """b'\\x00' encodes an empty list and decodes to it consuming 1 byte."""
        values, read = decode_vlenint(b'\x00')
        assert values == []
        assert read == 1

    def test_returns_tuple(self):
        """Result is a (list[int], int) tuple."""
        encoded = encode_vlenint([1, 2, 3])
        result = decode_vlenint(encoded)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_decoded_data_is_list_of_ints(self):
        """First element is a list of int."""
        encoded = encode_vlenint([0, 10, 10000])
        values, _ = decode_vlenint(encoded)
        assert isinstance(values, list)
        for v in values:
            assert isinstance(v, int)

    def test_read_bytes_count(self):
        """Second element is the number of bytes consumed from the buffer."""
        encoded = encode_vlenint([0, 10, 10000])
        _, read = decode_vlenint(encoded)
        assert read == len(encoded)

    def test_read_bytes_with_extra_trailing_data(self):
        """When buffer has extra bytes after the encoded payload, read count equals payload length."""
        encoded = encode_vlenint([42, 9999])
        padded = encoded + b'\xff\xff\xff'
        _, read = decode_vlenint(padded)
        assert read == len(encoded)

    def test_truncated_bit2_raises(self):
        """Not enough bytes for the count in the prefix raises ValueError."""
        with pytest.raises(ValueError, match="Data truncated"):
            decode_vlenint(b'\x03')

    def test_truncated_vint_prefix_raises(self):
        """A truncated vint count prefix surfaces as a decode error."""
        with pytest.raises(ValueError, match="Data truncated|Invalid opcode"):
            decode_vlenint(b'\x80')

    def test_truncated_values_raise(self):
        """Value bytes cut short raise ValueError."""
        encoded = encode_vlenint([5, 100000])
        with pytest.raises(ValueError, match="Data truncated"):
            decode_vlenint(encoded[:-1])

    @pytest.mark.parametrize("values, value_width, cut", [
        # 2-byte value cut to 1 byte
        ([5, 65535], 2, 1),
        # 3-byte value cut to 2 / 1 bytes
        ([5, 100000], 3, 1),
        ([5, 100000], 3, 2),
        # 4-byte value cut to 2 / 1 bytes
        ([1, 2 ** 32 - 1], 4, 2),
        ([1, 2 ** 32 - 1], 4, 3),
    ])
    def test_truncated_mid_value(self, values, value_width, cut):
        """The values section is cut inside the last multi-byte value."""
        encoded = encode_vlenint(values)
        with pytest.raises(
            ValueError,
            match=rf"expected {value_width} bytes of little-endian integer, got {value_width - cut}",
        ):
            decode_vlenint(encoded[:-cut])

    @pytest.mark.parametrize("values, tail_width", [
        # cut exactly before the last 1-byte value
        ([5, 65535, 7], 1),
        # cut exactly before the last 2-byte value
        ([5, 100000, 65535], 2),
    ])
    def test_truncated_between_values(self, values, tail_width):
        """The values section is cut exactly on a value boundary, the tail value is fully missing."""
        encoded = encode_vlenint(values)
        with pytest.raises(
            ValueError,
            match=rf"expected {tail_width} bytes of little-endian integer, got 0",
        ):
            decode_vlenint(encoded[:-tail_width])

    def test_byte_length_count_mismatch_raises(self):
        """The bit2 section holding more byte-lengths than the prefix declares raises ValueError."""
        # byte-lengths stream holds a run of 5 x byte_length=1, prefix
        # declares only 2, then 5 value bytes follow
        bit2_part = encode_bit2([1] * 5, ext8=True)
        corrupted = bytes([2]) + bit2_part[1:] + b'\x01\x02\x03\x04\x05'
        with pytest.raises(ValueError, match="Value count mismatch"):
            decode_vlenint(corrupted)


# ==============================================================================
# Self-describing format: [bit2(count + byte-lengths)][values]
# ==============================================================================


class TestSelfDescribing:
    """The bit2 count prefix makes the payload decodable without external input."""

    def test_exact_byte_format(self):
        """Verify the exact layout for trivial inputs, count is written by bit2coding."""
        assert encode_vlenint([]) == b'\x00'
        assert encode_vlenint([0]) == b'\x01\x00'
        assert encode_vlenint([5]) == b'\x01\x01\x05'

    @pytest.mark.parametrize("count", [1, 2, 3, 63, 127])
    def test_count_prefix_single_byte(self, count):
        """Counts below 128 encode to a single vint byte equal to the count."""
        encoded = encode_vlenint([0] * count)
        assert encoded[0] == count

    @pytest.mark.parametrize("count, prefix", [
        (128, b'\x80\x00'),
        (200, b'\x80\x48'),
        (300, b'\x81\x2c'),
    ])
    def test_count_prefix_multi_byte(self, count, prefix):
        """Counts >= 128 encode to a multi-byte vint prefix."""
        encoded = encode_vlenint([0] * count)
        assert encoded[:len(prefix)] == prefix

    def test_concatenated_payloads_decode_sequentially(self):
        """Self-describing payloads can be concatenated and decoded in order."""
        payload1 = encode_vlenint([0, 1, 255, 65536])
        payload2 = encode_vlenint([2 ** 32 - 1, 0])
        payload3 = encode_vlenint([])
        data = payload1 + payload2 + payload3
        values1, read1 = decode_vlenint(data)
        assert values1 == [0, 1, 255, 65536]
        assert read1 == len(payload1)
        values2, read2 = decode_vlenint(data[read1:])
        assert values2 == [2 ** 32 - 1, 0]
        assert read2 == len(payload2)
        values3, read3 = decode_vlenint(data[read1 + read2:])
        assert values3 == []
        assert read3 == len(payload3)


# ==============================================================================
# Specific encode/decode values (known structure)
# ==============================================================================


class TestKnownValues:
    """Verify encoding produces expected round-trip for known inputs."""

    def test_single_zero(self):
        """Encode [0] then decode back."""
        encoded = encode_vlenint([0])
        values, read = decode_vlenint(encoded)
        assert values == [0]
        assert read == len(encoded)

    def test_single_value_1(self):
        """Encode [1] then decode back."""
        encoded = encode_vlenint([1])
        values, read = decode_vlenint(encoded)
        assert values == [1]
        assert read == len(encoded)

    def test_two_zeros(self):
        """Encode [0, 0] then decode back."""
        encoded = encode_vlenint([0, 0])
        values, read = decode_vlenint(encoded)
        assert values == [0, 0]
        assert read == len(encoded)

    def test_zero_and_onehundred(self):
        """Encode [0, 100] then decode back."""
        encoded = encode_vlenint([0, 100])
        values, read = decode_vlenint(encoded)
        assert values == [0, 100]
        assert read == len(encoded)

    def test_zero_and_one(self):
        """Encode [0, 1] then decode back."""
        encoded = encode_vlenint([0, 1])
        values, read = decode_vlenint(encoded)
        assert values == [0, 1]
        assert read == len(encoded)

    def test_multiple_zeros_with_nonzero_mix(self):
        """A sequence with zeros and positive values decodes correctly."""
        encoded = encode_vlenint([0, 0, 0, 5, 0, 0, 0, 0])
        values, read = decode_vlenint(encoded)
        assert values == [0, 0, 0, 5, 0, 0, 0, 0]
        assert read == len(encoded)


# ==============================================================================
# Round-trip: encode_vlenint + decode_vlenint
# ==============================================================================


class TestRoundtrip:
    """``decode_vlenint(encode_vlenint(data))[0] == data``."""

    ROUNDTRIP_CASES = [
        # Empty
        [],
        # Zeros
        [0],
        [0, 0],
        [0, 0, 0, 0, 0],
        # Single values at key boundaries
        [1],
        [127],
        [255],
        [256],
        [65535],
        [65536],
        [16777215],
        [16777216],
        [2 ** 32 - 1],
        # Mix across byte-length boundaries
        [0, 1, 255, 256, 65535, 65536],
        [0, 0, 1, 1, 255, 255],
        [100, 200, 300, 40000, 500000],
        # Dense range
        list(range(10)),
        list(range(256)),
        # Alternating zeros and large values
        [0, 2 ** 16, 0, 2 ** 16, 0],
        [0, 2 ** 32 - 1, 0],
        # Mostly zeros
        [0] * 100,
        # Large values only
        [2 ** 32 - 1, 2 ** 32 - 1],
        [2 ** 24, 2 ** 16, 2 ** 8],
    ]

    @pytest.mark.parametrize("data", ROUNDTRIP_CASES)
    def test_roundtrip(self, data):
        """``decode_vlenint(encode_vlenint(data))[0] == data``."""
        encoded = encode_vlenint(data)
        decoded, read = decode_vlenint(encoded)
        assert decoded == data
        assert read == len(encoded)

    def test_roundtrip_boundary_byte_lengths(self):
        """Verify all five byte-length classes (0, 1, 2, 3, 4)."""
        # 0: 0
        # 1: 5
        # 2: 1000
        # 3: 200000
        # 4: 3000000000
        data = [0, 5, 1000, 200000, 3000000000]
        encoded = encode_vlenint(data)
        decoded, read = decode_vlenint(encoded)
        assert decoded == data
        assert read == len(encoded)

    @pytest.mark.parametrize("shift, offset", [
        (s, o) for s in range(0, 33) for o in (-1, 0, 1)
    ])
    def test_roundtrip_powers_of_two(self, shift, offset):
        """Round-trip for values near powers of two (2^0 .. 2^32 +/- 1)."""
        v = (1 << shift) + offset
        if v < 0 or v > 2 ** 32 - 1:
            pytest.skip("Value out of valid range")
        encoded = encode_vlenint([v])
        decoded, read = decode_vlenint(encoded)
        assert decoded == [v], f"Round-trip failed for {v} (2^{shift} + {offset})"
        assert read == len(encoded)

    def test_roundtrip_repeated_same_byte_length(self):
        """Many values with the same byte length benefit from bit2 run encoding."""
        data = [5] * 50  # all are byte_length=1
        encoded = encode_vlenint(data)
        decoded, read = decode_vlenint(encoded)
        assert decoded == data
        assert read == len(encoded)

    def test_roundtrip_large_constant_zero(self):
        """A large run of zeros compresses well via bit2 run encoding."""
        data = [0] * 200
        encoded = encode_vlenint(data)
        decoded, _ = decode_vlenint(encoded)
        assert decoded == data

    def test_roundtrip_large_mixed_values(self):
        """Large mixed dataset round-trips correctly."""
        data = []
        for i in range(500):
            # Mix zeros and various-length values
            if i % 10 == 0:
                data.append(0)
            elif i % 10 == 1:
                data.append(2 ** 16 - 1)
            elif i % 10 == 2:
                data.append(2 ** 24)
            elif i % 10 == 3:
                data.append(2 ** 32 - 1)
            else:
                data.append(i * 1000)
        encoded = encode_vlenint(data)
        decoded, _ = decode_vlenint(encoded)
        assert decoded == data
