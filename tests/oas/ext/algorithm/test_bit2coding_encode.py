"""
Tests for the top-level ``encode_bit2`` and ``decode_bit2`` convenience wrappers.

These are thin wrappers around the well-tested iterator functions:
  - ``encode_bit2(data)`` → bytes, with a vint count prefix (see ``encode_vint``)
  - ``decode_bit2(data)`` → (list[int], int), count read from the prefix

The underlying iterators (``encode_bit2_opcode_iter``, ``encode_bit2_stream_iter``,
``decode_bit2_stream_iter``, ``decode_bit2_opcode``) have comprehensive coverage
elsewhere; this file verifies the wrappers behave correctly end-to-end.
"""

import pytest

from oas.ext.algorithm.bit2coding import decode_bit2, encode_bit2, encode_bit2_stream_iter

# ==============================================================================
# encode_bit2 — return type and basic structure
# ==============================================================================


class TestEncodeBit2:
    """``encode_bit2(data) → bytes``."""

    def test_empty_encodes_count_zero(self):
        """Empty input produces the vint count prefix alone (count=0)."""
        assert encode_bit2([]) == b"\x00"

    def test_returns_bytes(self):
        """Result is always bytes, not list[int] or generator."""
        result = encode_bit2([1, 2, 3])
        assert isinstance(result, bytes)

    def test_single_values(self):
        """Single values encode to the count byte plus a single byte."""
        for val in range(4):
            result = encode_bit2([val])
            assert result == bytes([1, val])

    def test_two_values(self):
        """Two values use the 2-item literal format."""
        result = encode_bit2([1, 2])
        # count=2, then 16 + 1*4 + 2 = 22
        assert result == bytes([2, 22])

    def test_deterministic(self):
        """Same input produces identical bytes."""
        data = [0, 1, 2, 3, 0, 0, 0, 0, 1, 1, 1, 1]
        assert encode_bit2(data) == encode_bit2(data)


# ==============================================================================
# decode_bit2 — return type and basic structure
# ==============================================================================


class TestDecodeBit2:
    """``decode_bit2(data) → (list[int], int)``."""

    def test_empty_input_raises(self):
        """Empty data is not a valid encoding, the vint count prefix is missing."""
        with pytest.raises(ValueError, match="Data truncated"):
            decode_bit2(b"")

    def test_decode_empty_list_encoding(self):
        """b'\\x00' encodes an empty list and decodes to it consuming 1 byte."""
        data, read = decode_bit2(b"\x00")
        assert data == []
        assert read == 1

    def test_returns_tuple(self):
        """Result is a (list[int], int) tuple."""
        encoded = encode_bit2([1, 2, 3])
        result = decode_bit2(encoded)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_decoded_data_is_list_of_ints(self):
        """First element is a list of int, each 0-3."""
        encoded = encode_bit2([0, 1, 2, 3])
        data, _ = decode_bit2(encoded)
        assert isinstance(data, list)
        for v in data:
            assert isinstance(v, int)
            assert 0 <= v <= 3

    def test_read_bytes_count(self):
        """Second element is the number of bytes consumed."""
        encoded = encode_bit2([0, 1, 2, 3])
        _, read = decode_bit2(encoded)
        assert read == len(encoded)

    def test_read_bytes_with_extra_trailing_data(self):
        """When buffer has extra bytes after the encoded payload, read count equals payload length."""
        encoded = encode_bit2([0, 1, 2, 3])
        padded = encoded + b"\xff\xff\xff"
        _, read = decode_bit2(padded)
        assert read == len(encoded)

    def test_truncated_data_raises(self):
        """Not enough bytes for the count in the prefix raises ValueError."""
        with pytest.raises(ValueError, match="Data truncated"):
            decode_bit2(b"\x03")

    def test_truncated_vint_prefix_raises(self):
        """A truncated vint count prefix surfaces as a decode error."""
        with pytest.raises(ValueError, match="Data truncated|Invalid opcode"):
            decode_bit2(b"\x80")

    def test_invalid_opcode_raises(self):
        """Byte with value 4-15 (invalid) raises ValueError."""
        with pytest.raises(ValueError, match="Invalid opcode"):
            decode_bit2(bytes([1, 5]))

    def test_stream_exceeding_declared_count_raises(self):
        """A run opcode crossing the declared count raises ValueError.

        decode_bit2_stream_iter may return more values than requested when
        a run opcode crosses the total boundary, which only happens when the
        stream does not match the count prefix (truncated or corrupted input).
        """
        # stream encodes a run of 5 zeros, prefix declares only 3
        with pytest.raises(ValueError, match="Value count mismatch"):
            decode_bit2(b"\x03\x82")

    def test_copy_crossing_declared_count_raises(self):
        """A copy opcode crossing the declared count raises ValueError.

        Like a run opcode, a copy opcode adds its full length to the count
        at once and may jump from below total to above it, expanding more
        values than the prefix declares (corrupted or truncated input).
        """
        # count=2, literal [1], then copy offset=1 length=4 -> 5 values total
        with pytest.raises(ValueError, match="Value count mismatch"):
            decode_bit2(b"\x02\x01\x43\x00")

    def test_pack_padding_slots_do_not_add_values(self):
        """Corrupting the padding slots of a pack byte never changes the count.

        A pack literal declares n items and reads ceil(n/4) bytes; the
        trailing byte has padding slots ignored by the decoder, so a mutation
        there changes values but not the decoded count.
        """
        items = [1, 2, 3, 0] * 4 + [1, 2]  # 18 items -> 5 bytes, 2 padding slots
        stream = bytes(encode_bit2_stream_iter([(0, items)]))
        payload = bytes([len(items)]) + stream
        # flip the padding slots of the last byte
        mutated = payload[:-1] + bytes([payload[-1] ^ 0x0F])
        decoded, read = decode_bit2(mutated)
        assert len(decoded) == len(items)
        assert read == len(payload)

    def test_pack_declared_count_mutation_raises(self):
        """Mutating the declared item count of a pack opcode raises ValueError.

        The opcode declares n items and the decoder fills exactly n slots, so
        a corrupted declaration yields more values than the prefix total.
        """
        items = [1, 2, 3, 0] * 4 + [1, 2]  # 18 items -> 5 bytes hold 20 slots
        stream = bytes(encode_bit2_stream_iter([(0, items)]))
        # declare 20 items instead of 18
        corrupted = bytes([len(items)]) + bytes([29 + 20]) + stream[1:]
        with pytest.raises(ValueError, match="Value count mismatch"):
            decode_bit2(corrupted)


# ==============================================================================
# Self-describing format: [vint count][bit2 stream]
# ==============================================================================


class TestSelfDescribing:
    """The vint count prefix makes the payload decodable without external input."""

    @pytest.mark.parametrize("count", [1, 2, 3, 63, 127])
    def test_count_prefix_single_byte(self, count):
        """Counts below 128 encode to a single vint byte equal to the count."""
        encoded = encode_bit2([0] * count)
        assert encoded[0] == count

    @pytest.mark.parametrize("count, prefix", [
        (128, b"\x80\x00"),
        (200, b"\x80\x48"),
        (300, b"\x81\x2c"),
    ])
    def test_count_prefix_multi_byte(self, count, prefix):
        """Counts >= 128 encode to a multi-byte vint prefix."""
        encoded = encode_bit2([0] * count)
        assert encoded[:len(prefix)] == prefix

    def test_concatenated_payloads_decode_sequentially(self):
        """Self-describing payloads can be concatenated and decoded in order."""
        payload1 = encode_bit2([0, 1, 2, 3])
        payload2 = encode_bit2([2] * 20)
        payload3 = encode_bit2([])
        data = payload1 + payload2 + payload3
        values1, read1 = decode_bit2(data)
        assert values1 == [0, 1, 2, 3]
        assert read1 == len(payload1)
        values2, read2 = decode_bit2(data[read1:])
        assert values2 == [2] * 20
        assert read2 == len(payload2)
        values3, read3 = decode_bit2(data[read1 + read2:])
        assert values3 == []
        assert read3 == len(payload3)


# ==============================================================================
# Round-trip: encode_bit2 + decode_bit2
# ==============================================================================


class TestRoundtrip:
    """``decode_bit2(encode_bit2(data))[0] == data``."""

    ROUNDTRIP_CASES = [
        # Empty
        [],
        # Singletons
        [0],
        [1],
        [2],
        [3],
        # Small sequences
        [0, 1, 2, 3],
        [3, 2, 1, 0],
        [0, 1, 0, 1],
        [1, 2, 1, 2],
        [0, 1, 2, 0, 1, 2],
        # Run (4+ identical)
        [0, 0, 0, 0],
        [1, 1, 1, 1, 1],
        [2, 2, 2, 2, 2, 2, 2],
        [3] * 10,
        # Mixed
        [0, 0, 0, 0, 1, 1, 1, 1],
        [0, 0, 0, 0, 1, 2, 3],
        [0, 1, 2, 3, 0, 0, 0, 0],
        # Longer runs, copies, patterns
        [0, 1] * 15,
        [1, 2, 3] * 10,
        [0, 1, 2, 3] * 25,
        # Large constant
        [2] * 50,
        [0] * 100,
        # Long literal sequence
        [i % 4 for i in range(50)],
        # Sawtooth
        [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3],
        # Descending
        [3, 2, 1, 0, 3, 2, 1, 0],
    ]

    @pytest.mark.parametrize("data", ROUNDTRIP_CASES)
    def test_roundtrip(self, data):
        """``decode_bit2(encode_bit2(data))[0] == data``."""
        encoded = encode_bit2(data)
        decoded, read = decode_bit2(encoded)
        assert decoded == data
        assert read == len(encoded)

    def test_roundtrip_large_synthetic(self):
        """Large synthetic data round-trips correctly."""
        data = []
        for i in range(200):
            if i % 7 == 0:
                data.extend([i % 4] * 5)  # run
            else:
                data.append(i % 4)         # literal
        encoded = encode_bit2(data)
        decoded, read = decode_bit2(encoded)
        assert decoded == data
        assert read == len(encoded)

    def test_roundtrip_large_constant(self):
        """Large constant run round-trips correctly."""
        data = [3] * 400
        encoded = encode_bit2(data)
        decoded, _ = decode_bit2(encoded)
        assert decoded == data

    def test_roundtrip_repeating_pattern(self):
        """Repeating 3-value pattern round-trips correctly."""
        data = [1, 2, 3] * 200
        encoded = encode_bit2(data)
        decoded, _ = decode_bit2(encoded)
        assert decoded == data

    def test_roundtrip_cycling_values(self):
        """Cycling 0-3 sequence round-trips correctly."""
        data = [i % 4 for i in range(200)]
        encoded = encode_bit2(data)
        decoded, _ = decode_bit2(encoded)
        assert decoded == data
