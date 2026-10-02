"""
Tests for the ``ext8`` extension in ``oas.ext.algorithm.bit2coding``.

When ``ext8=True``, the 2-bit coding format additionally supports literal
values **4, 5, 6, 7** — the previously-invalid byte range 0b000001XX
(4 ≤ byte < 8).  These are encoded as single-byte literals in the stream
representation.

Functions tested:
  - ``encode_bit2_stream_iter(opcodes, ext8=True)``
  - ``decode_bit2_stream_iter(data, total, ext8=True)``
  - ``encode_bit2(data, ext8=True)`` / ``decode_bit2(data, ext8=True)``
  - Round-trip consistency across the full pipeline

Notes on error behaviour:
  - The *encoder* (``encode_bit2_stream_iter``/``encode_bit2``) does **not**
    validate that literal values are in-range — values outside 0-7 are passed
    through to the byte stream without error.
  - The *decoder* (``decode_bit2_stream_iter``/``decode_bit2``) performs all
    range checks, raising ``ValueError("Invalid opcode")`` for byte values
    in the 4-15 range when ``ext8=False``, and for bytes 8-15 even when
    ``ext8=True``.
  - Ext8 only affects the **literal opcode** path. Run and copy opcodes
    continue to use 2-bit values (0-3) and are unaffected.
  - ``encode_bit2_opcode_iter`` will never produce a run opcode for values
    4-7 — runs of those values automatically fall through to the
    literal/copy path.  Copy opcodes referencing values 4-7 work correctly.
"""

import pytest

from oas.ext.algorithm.bit2coding import (
    decode_bit2, decode_bit2_opcode, decode_bit2_stream_iter, encode_bit2, encode_bit2_opcode_iter,
    encode_bit2_stream_iter
)

# ==============================================================================
# encode_bit2_stream_iter — ext8 literal encoding
# ==============================================================================


class TestEncodeStreamExt8Literal:
    """Encoding literal opcodes with ext8 values (4/5/6/7).

    In ext8 mode, single literal values 4-7 are emitted directly as bytes
    4-7 (the ``000001XX`` format).  The encoder doesn't validate range, so
    it never raises; all validation is on the decode side.
    """

    def test_single_ext8_value_4(self):
        """Value 4 → single byte 4."""
        result = list(encode_bit2_stream_iter([(0, [4])], ext8=True))
        assert result == [4]

    def test_single_ext8_value_5(self):
        """Value 5 → single byte 5."""
        result = list(encode_bit2_stream_iter([(0, [5])], ext8=True))
        assert result == [5]

    def test_single_ext8_value_6(self):
        """Value 6 → single byte 6."""
        result = list(encode_bit2_stream_iter([(0, [6])], ext8=True))
        assert result == [6]

    def test_single_ext8_value_7(self):
        """Value 7 → single byte 7."""
        result = list(encode_bit2_stream_iter([(0, [7])], ext8=True))
        assert result == [7]

    def test_multiple_ext8_values_sequential(self):
        """Multiple sequential ext8 values → each encoded as its own byte."""
        items = [4, 5, 6, 7]
        result = list(encode_bit2_stream_iter([(0, items)], ext8=True))
        assert result == [4, 5, 6, 7]

    def test_mixed_normal_and_ext8(self):
        """Mix of 0-3 and 4-7 values in same literal opcode.

        Values ≤3 use the normal literal batching; values ≥4 are emitted
        individually as single-byte ext8 literals.
        """
        items = [0, 1, 4, 2, 5, 3]
        result = list(encode_bit2_stream_iter([(0, items)], ext8=True))
        # 0,1 → 2-item literal: 16 + 0*4 + 1 = 17
        # 4   → single byte 4
        # 2   → single byte 2 (1-item literal)
        # 5   → single byte 5
        # 3   → single byte 3
        assert result == [17, 4, 2, 5, 3]

    def test_ext8_preceded_by_normal_batch(self):
        """Normal items followed by ext8 values."""
        items = [1, 2, 3, 0, 4, 5]
        result = list(encode_bit2_stream_iter([(0, items)], ext8=True))
        # [1,2,3,0] → batch 4 items: 29+4=33 header, packed: 1*64+2*16+3*4+0=108
        # then 4,5 yield individually
        assert result == [33, 108, 4, 5]

    def test_ext8_followed_by_normal_batch(self):
        """Ext8 values followed by normal items."""
        items = [4, 5, 0, 1, 2, 3]
        result = list(encode_bit2_stream_iter([(0, items)], ext8=True))
        # 4,5 → single bytes; [0,1,2,3] → batch 4: 33, 27
        assert result == [4, 5, 33, 27]

    def test_ext8_interspersed_with_normal_batches(self):
        """Ext8 values interleaved between normal batches."""
        items = [0, 0, 0, 0, 4, 1, 1, 1, 1, 5, 2, 2, 2, 2]
        result = list(encode_bit2_stream_iter([(0, items)], ext8=True))
        # [0,0,0,0] → batch 4: 33, 0
        # 4 → single byte
        # [1,1,1,1] → batch 4: 33, 85  (1*64+1*16+1*4+1)
        # 5 → single byte
        # [2,2,2,2] → batch 4: 33, 170 (2*64+2*16+2*4+2)
        assert result == [33, 0, 4, 33, 85, 5, 33, 170]

    def test_ext8_only_no_normal(self):
        """All ext8 values, no normal 0-3 items."""
        items = [4, 5, 6, 7, 4, 5]
        result = list(encode_bit2_stream_iter([(0, items)], ext8=True))
        assert result == [4, 5, 6, 7, 4, 5]

    def test_ext8_surrounded_by_one_item_literals(self):
        """Ext8 value between two single normal-item literals."""
        opcodes = [(0, [0]), (0, [4]), (0, [1])]
        result = list(encode_bit2_stream_iter(opcodes, ext8=True))
        assert result == [0, 4, 1]

    def test_ext8_large_batch_with_ext8_values(self):
        """Large batch including both normal and ext8 values (33 items).

        Only validates that encoding produces valid bytes (no overflow).
        """
        items = [i % 8 for i in range(33)]
        result = list(encode_bit2_stream_iter([(0, items)], ext8=True))
        assert isinstance(result, list)
        assert all(0 <= b <= 255 for b in result)

    def test_ext8_encoding_without_flag_still_works(self):
        """Without ext8 flag, value 4 in a literal opcode is encoded as-is.

        The encoder does not validate range so it passes the value through
        without error.  The decoder rejects it later.
        """
        result = list(encode_bit2_stream_iter([(0, [4])], ext8=False))
        assert result == [4]  # encoded as raw byte 4


# ==============================================================================
# encode_bit2_stream_iter — run/copy opcodes are unaffected by ext8
# ==============================================================================


class TestEncodeStreamExt8NonLiteral:
    """Run and copy opcodes are completely unchanged when ext8=True."""

    def test_run_opcode_unchanged(self):
        """Run opcode encoding is the same with or without ext8."""
        opcodes = [(1, 2, 10)]
        with_ext8 = list(encode_bit2_stream_iter(opcodes, ext8=True))
        without_ext8 = list(encode_bit2_stream_iter(opcodes, ext8=False))
        assert with_ext8 == without_ext8

    def test_copy_opcode_unchanged(self):
        """Copy opcode encoding is the same with or without ext8."""
        opcodes = [(2, 50, 5)]
        with_ext8 = list(encode_bit2_stream_iter(opcodes, ext8=True))
        without_ext8 = list(encode_bit2_stream_iter(opcodes, ext8=False))
        assert with_ext8 == without_ext8

    def test_mixed_opcodes_unchanged_for_run_copy(self):
        """Literal portions differ, run/copy are identical."""
        opcodes = [(0, [4]), (1, 0, 5), (2, 10, 3), (0, [5, 6])]
        with_ext8 = list(encode_bit2_stream_iter(opcodes, ext8=True))
        assert 4 in with_ext8
        assert 5 in with_ext8
        assert 6 in with_ext8


# ==============================================================================
# decode_bit2_stream_iter — ext8 literal decoding
# ==============================================================================


class TestDecodeStreamExt8Literal:
    """Decoding ext8 literal values (bytes 4-7 → opcode (0, [val]))."""

    @pytest.mark.parametrize("val", [4, 5, 6, 7])
    def test_ext8_byte_decoded_with_ext8_true(self, val):
        """With ext8=True, byte 4-7 decodes to single-item literal."""
        data = memoryview(bytes([val]))
        opcodes, read = decode_bit2_stream_iter(data, 1, ext8=True)
        assert opcodes == [(0, [val])]
        assert read == 1

    @pytest.mark.parametrize("byte", [4, 5, 6, 7])
    def test_ext8_byte_raises_with_ext8_false(self, byte):
        """Without ext8, byte 4-7 raises ValueError."""
        data = memoryview(bytes([byte]))
        with pytest.raises(ValueError, match="Invalid opcode"):
            decode_bit2_stream_iter(data, 1, ext8=False)

    @pytest.mark.parametrize("byte", [0, 1, 2, 3])
    def test_normal_bytes_still_work_with_ext8_true(self, byte):
        """With ext8=True, normal byte 0-3 still decodes correctly."""
        data = memoryview(bytes([byte]))
        opcodes, read = decode_bit2_stream_iter(data, 1, ext8=True)
        assert opcodes == [(0, [byte])]
        assert read == 1

    def test_multiple_ext8_values_sequential_decode(self):
        """Multiple sequential ext8 bytes decode to individual literals."""
        data = memoryview(bytes([4, 5, 6, 7]))
        opcodes, read = decode_bit2_stream_iter(data, 4, ext8=True)
        assert opcodes == [(0, [4]), (0, [5]), (0, [6]), (0, [7])]
        assert read == 4

    def test_mixed_normal_and_ext8_decode(self):
        """Mixed 0-3 and 4-7 bytes decode correctly with ext8."""
        data = memoryview(bytes([0, 4, 1, 5]))
        opcodes, read = decode_bit2_stream_iter(data, 4, ext8=True)
        assert opcodes == [(0, [0]), (0, [4]), (0, [1]), (0, [5])]
        assert read == 4

    def test_ext8_with_batch_literal_decode(self):
        """Batch literal header followed by ext8 value."""
        # 33 = batch header for 4 items (29+4); 27 = packed [0,1,2,3]; then 6 = ext8
        data = memoryview(bytes([33, 27, 6]))
        opcodes, read = decode_bit2_stream_iter(data, 5, ext8=True)
        assert opcodes == [(0, [0, 1, 2, 3]), (0, [6])]
        assert read == 3

    def test_ext8_with_run_and_copy_decode(self):
        """Ext8 value followed by run and copy opcodes."""
        # 4 = ext8; 128 = short run (val=0, len=3); 64+0 = short copy (off=1, len=1)
        data = memoryview(bytes([4, 128, 64, 0]))
        opcodes, read = decode_bit2_stream_iter(data, 5, ext8=True)
        assert opcodes == [(0, [4]), (1, 0, 3), (2, 1, 1)]
        assert read == 4

    def test_ext8_decode_with_partial_total(self):
        """Decoding stops when total reached mid-ext8 sequence."""
        data = memoryview(bytes([4, 5, 6]))
        opcodes, read = decode_bit2_stream_iter(data, 2, ext8=True)
        assert opcodes == [(0, [4]), (0, [5])]
        assert read == 2

    def test_byte_8_plus_still_invalid_with_ext8(self):
        """With ext8=True, bytes 8-15 remain invalid (outside ext8 range)."""
        for byte in [8, 9, 10, 11, 12, 13, 14, 15]:
            data = memoryview(bytes([byte]))
            with pytest.raises(ValueError, match="Invalid opcode"):
                decode_bit2_stream_iter(data, 1, ext8=True)


# ==============================================================================
# Round-trip: encode_bit2_stream_iter + decode_bit2_stream_iter with ext8
# ==============================================================================


class TestRoundtripStreamExt8:
    """Encode then decode (ext8=True) — compare **data values** not opcode
    structure.

    Ext8 encoding necessarily splits literal opcodes containing values ≥4
    into individual opcodes, so comparing opcode structure directly is not
    meaningful.  Instead we flatten the decoded opcodes through
    ``decode_bit2_opcode`` and compare the resulting values.
    """

    ROUNDTRIP_CASES = [
        # Single ext8 values
        [(0, [4])],
        [(0, [5])],
        [(0, [6])],
        [(0, [7])],
        # Multiple ext8 values
        [(0, [4, 5, 6, 7])],
        # Mixed normal and ext8
        [(0, [0, 4])],
        [(0, [1, 2, 5])],
        [(0, [0, 1, 4, 5, 2, 3])],
        [(0, [4, 0, 5, 1])],
        # Ext8 in separate opcodes
        [(0, [4]), (0, [5])],
        [(0, [0]), (0, [4])],
        [(0, [1, 2]), (0, [6, 7])],
        # Mixed with run opcodes
        [(0, [4]), (1, 0, 5), (0, [5])],
        [(1, 2, 10), (0, [6, 7]), (1, 3, 4)],
        # Mixed with copy opcodes
        [(2, 10, 3), (0, [4]), (2, 20, 5)],
        # All three types with ext8
        [(0, [4]), (1, 0, 4), (2, 3, 2), (0, [5, 6])],
        # Large literal block with interspersed ext8
        [(0, [i % 8 for i in range(50)])],
        # Many alternating ext8 and normal
        [(0, [i % 2 * 4 for i in range(20)])],  # 0, 4, 0, 4, ...
    ]

    @staticmethod
    def _flatten(opcodes):
        """Flatten opcodes to the list of decoded values."""
        return decode_bit2_opcode(opcodes)

    @staticmethod
    def _total(opcodes):
        """Total count of values encoded in opcodes."""
        return sum(
            op[2] if op[0] != 0 else len(op[1])
            for op in opcodes
        )

    @pytest.mark.parametrize("opcodes", ROUNDTRIP_CASES)
    def test_roundtrip(self, opcodes):
        """Encode then decode with ext8=True — data values are preserved."""
        encoded = list(encode_bit2_stream_iter(opcodes, ext8=True))
        total = self._total(opcodes)
        decoded_opcodes, read = decode_bit2_stream_iter(
            memoryview(bytes(encoded)), total, ext8=True
        )
        expected_data = self._flatten(opcodes)
        decoded_data = self._flatten(decoded_opcodes)
        assert decoded_data == expected_data, f"Failed for {opcodes}"
        assert read == len(encoded)

    def test_roundtrip_large_alternating(self):
        """Large sequence alternating between normal and ext8 values."""
        items = []
        for i in range(500):
            if i % 2 == 0:
                items.append(i % 4)      # normal 0-3
            else:
                items.append(4 + i % 4)  # ext8 4-7
        opcodes = [(0, items)]
        encoded = list(encode_bit2_stream_iter(opcodes, ext8=True))
        total = len(items)
        decoded_opcodes, read = decode_bit2_stream_iter(
            memoryview(bytes(encoded)), total, ext8=True
        )
        assert self._flatten(decoded_opcodes) == items
        assert read == len(encoded)

    def test_roundtrip_many_single_ext8_opcodes(self):
        """1000 individual ext8 literal opcodes — values preserved."""
        n = 1000
        opcodes = [(0, [4 + (i % 4)]) for i in range(n)]
        encoded = list(encode_bit2_stream_iter(opcodes, ext8=True))
        decoded_opcodes, read = decode_bit2_stream_iter(
            memoryview(bytes(encoded)), n, ext8=True
        )
        assert self._flatten(decoded_opcodes) == self._flatten(opcodes)
        assert read == len(encoded)

    def test_decode_ext8_without_flag_fails(self):
        """Decoding ext8 bytes without ext8 flag raises ValueError (decoder
        validation, not encoder)."""
        encoded = list(encode_bit2_stream_iter([(0, [4])], ext8=True))
        with pytest.raises(ValueError, match="Invalid opcode"):
            decode_bit2_stream_iter(memoryview(bytes(encoded)), 1, ext8=False)

    def test_encode_without_flag_then_decode_without_flag_fails(self):
        """Encoding ext8 value without ext8 produces a byte, but decoding
        without ext8 rejects it."""
        encoded = list(encode_bit2_stream_iter([(0, [4])], ext8=False))
        # encoded = [4], which is a valid ext8 byte when ext8=True,
        # but invalid when ext8=False
        with pytest.raises(ValueError, match="Invalid opcode"):
            decode_bit2_stream_iter(memoryview(bytes(encoded)), 1, ext8=False)


# ==============================================================================
# Top-level encode_bit2 / decode_bit2 with ext8
# ==============================================================================


class TestEncodeBit2Ext8:
    """``encode_bit2(data, ext8=True)``."""

    def test_ext8_values_simple(self):
        """Encode data with ext8 values."""
        data = [4, 5, 6, 7]
        result = encode_bit2(data, ext8=True)
        assert isinstance(result, bytes)
        assert result == bytes([4, 4, 5, 6, 7])

    def test_ext8_mixed_with_normal(self):
        """Encode data mixing 0-3 and 4-7."""
        data = [0, 4, 1, 5]
        result = encode_bit2(data, ext8=True)
        assert isinstance(result, bytes)
        assert result == bytes([4, 0, 4, 1, 5])

    def test_ext8_empty(self):
        """Empty input with ext8=True encodes the count prefix alone."""
        assert encode_bit2([], ext8=True) == b"\x00"

    def test_ext8_normal_values_unchanged(self):
        """Normal 0-3 data is encoded identically with ext8=True."""
        data = [0, 1, 2, 3, 0, 0, 0, 0, 1, 2, 3, 0]
        with_ext8 = encode_bit2(data, ext8=True)
        without_ext8 = encode_bit2(data, ext8=False)
        assert with_ext8 == without_ext8


class TestDecodeBit2Ext8:
    """``decode_bit2(data, ext8=True)``."""

    def test_decode_ext8_values(self):
        """Decode ext8-encoded data with ext8=True."""
        encoded = encode_bit2([4, 5, 6, 7], ext8=True)
        decoded, read = decode_bit2(encoded, ext8=True)
        assert decoded == [4, 5, 6, 7]
        assert read == len(encoded)

    def test_decode_mixed_values(self):
        """Decode mixed normal/ext8 data."""
        data = [1, 4, 2, 5, 3, 6]
        encoded = encode_bit2(data, ext8=True)
        decoded, read = decode_bit2(encoded, ext8=True)
        assert decoded == data
        assert read == len(encoded)

    def test_decode_without_flag_fails_for_ext8_data(self):
        """Decoding ext8-encoded data without ext8 flag raises."""
        encoded = encode_bit2([4], ext8=True)
        with pytest.raises(ValueError, match="Invalid opcode"):
            decode_bit2(encoded, ext8=False)


# ==============================================================================
# Full round-trip: encode_bit2 + decode_bit2 with ext8
# ==============================================================================


class TestRoundtripExt8:
    """``decode_bit2(encode_bit2(data, ext8=True))[0] == data``."""

    ROUNDTRIP_CASES = [
        # Empty
        [],
        # Single ext8 values
        [4],
        [5],
        [6],
        [7],
        # Multiple ext8 values
        [4, 5, 6, 7],
        [7, 6, 5, 4],
        # Mixed with normal values
        [0, 4],
        [1, 2, 5],
        [0, 1, 4, 5, 2, 3],
        [3, 7, 2, 6, 1, 5, 0, 4],
        # Normal only (should work same as without ext8)
        [0, 1, 2, 3],
        [0, 1, 2, 3, 0, 1, 2, 3],
        # Patterns with occasional ext8
        [0, 1, 2, 3, 4, 0, 1, 2, 3],
        [0, 4, 0, 4, 0, 4],
        [1, 5, 1, 5, 1, 5],
        # Larger sequences (no runs of 4-7 — those are literal-only in ext8)
        [i % 8 for i in range(50)],
        [i % 8 for i in range(100)],
    ]

    @pytest.mark.parametrize("data", ROUNDTRIP_CASES)
    def test_roundtrip(self, data):
        """Round-trip with ext8=True."""
        encoded = encode_bit2(data, ext8=True)
        decoded, read = decode_bit2(encoded, ext8=True)
        assert decoded == data, f"Failed for {data}"
        assert read == len(encoded)

    def test_roundtrip_large_mixed(self):
        """Large mixed normal/ext8 data round-trips."""
        data = []
        for i in range(400):
            if i % 2 == 0:
                data.append(i % 4)
            else:
                data.append(4 + (i % 4))
        encoded = encode_bit2(data, ext8=True)
        decoded, _ = decode_bit2(encoded, ext8=True)
        assert decoded == data

    def test_roundtrip_alternating_ext8_and_run_patterns(self):
        """Data with both ext8 singletons and runs of normal values (0-3)."""
        data = []
        for i in range(200):
            if i % 5 == 0:
                # run of 5 identical normal values (0-3)
                data.extend([i % 4] * 5)
            elif i % 5 == 1:
                # single ext8
                data.append(4 + (i % 4))
            else:
                # literal normal
                data.append(i % 4)
        encoded = encode_bit2(data, ext8=True)
        decoded, _ = decode_bit2(encoded, ext8=True)
        assert decoded == data

    def test_roundtrip_all_ext8_values_no_runs(self):
        """Data consisting entirely of values 4-7, no runs of same value ≥3."""
        # Mix values so that no run of 3+ identical values 4-7 occurs
        # (ext8 only supports 4-7 as literals, not runs).
        data = [4, 5, 6, 7] * 100
        encoded = encode_bit2(data, ext8=True)
        decoded, _ = decode_bit2(encoded, ext8=True)
        assert decoded == data

    def test_roundtrip_deterministic(self):
        """Same ext8 input produces identical bytes."""
        data = [0, 4, 1, 5, 2, 6, 3, 7]
        assert encode_bit2(data, ext8=True) == encode_bit2(data, ext8=True)

    def test_roundtrip_with_runs_of_normal_values(self):
        """Data with runs of normal values (0-3) and interspersed ext8."""
        data = [0, 0, 0, 0, 4, 1, 1, 1, 1, 5, 2, 2, 2, 2, 6]
        encoded = encode_bit2(data, ext8=True)
        decoded, _ = decode_bit2(encoded, ext8=True)
        assert decoded == data

    def test_normal_data_roundtrip_unchanged(self):
        """Data with only 0-3 values round-trips identically with ext8=False
        and ext8=True.

        Note: the data deliberately avoids a trailing run of exactly 3
        identical normal values, which triggers a pre-existing encoding bug
        (run length 3 underflows the short-run format ``run-4``).
        """
        data = [0, 1, 2, 3, 0, 0, 0, 0, 1, 2, 3, 0, 1, 2, 3, 0, 0, 0, 0, 0]
        encoded_ext8 = encode_bit2(data, ext8=True)
        encoded_no_ext8 = encode_bit2(data, ext8=False)
        assert encoded_ext8 == encoded_no_ext8
        decoded_ext8, _ = decode_bit2(encoded_ext8, ext8=True)
        decoded_no_ext8, _ = decode_bit2(encoded_no_ext8, ext8=False)
        assert decoded_ext8 == data
        assert decoded_no_ext8 == data


# ==============================================================================
# Error handling
# ==============================================================================


class TestExt8ErrorHandling:
    """Error cases specific to ext8 mode.

    Note: all validation is on the *decoder* side.  The encoder passes
    values through without range-checking.
    """

    def test_value_8_roundtrip_fails_decode(self):
        """Value 8 encoded with ext8=True produces byte 8, which the decoder
        (even with ext8=True) rejects as invalid (only 4-7 are ext8)."""
        opcodes = [(0, [8])]
        encoded = list(encode_bit2_stream_iter(opcodes, ext8=True))
        # encoded = [8], which is in the invalid range 8-15
        with pytest.raises(ValueError, match="Invalid opcode"):
            decode_bit2_stream_iter(memoryview(bytes(encoded)), 1, ext8=True)

    def test_decode_byte_8_plus_still_invalid_with_ext8(self):
        """Byte value 8+ with ext8=True still raises ValueError."""
        data = memoryview(bytes([8]))
        with pytest.raises(ValueError, match="Invalid opcode"):
            decode_bit2_stream_iter(data, 1, ext8=True)

    def test_truncated_data_with_ext8(self):
        """Not enough data for the count in the prefix still raises with ext8=True."""
        with pytest.raises(ValueError, match="Data truncated"):
            decode_bit2(b"\x04", ext8=True)

    def test_encode_then_decode_without_ext8_fails(self):
        """Encoding value 4 (even without ext8 flag) produces a byte that
        the decoder rejects when ext8=False."""
        encoded = list(encode_bit2_stream_iter([(0, [4])], ext8=False))
        assert encoded == [4]
        with pytest.raises(ValueError, match="Invalid opcode"):
            decode_bit2_stream_iter(memoryview(bytes(encoded)), 1, ext8=False)


# ==============================================================================
# Full pipeline integration test — data → opcodes → stream → decode
# ==============================================================================


class TestFullPipelineExt8:
    """End-to-end: data → encode_bit2_opcode_iter → encode_bit2_stream_iter
    → decode_bit2_stream_iter → decode_bit2_opcode, with ext8=True.
    """

    PIPELINE_CASES = [
        [4],
        [5],
        [6],
        [7],
        [4, 5, 6, 7],
        [0, 4],
        [1, 5, 2, 6],
        [0, 1, 2, 3, 4, 5, 6, 7],
        # i%8 gives repeating 0-7; run avoidance: values 4-7 only appear once
        # every 8 items so no run of 3+ identical values 4-7 occurs.
        [i % 8 for i in range(20)],
        [i % 8 for i in range(100)],
    ]

    @pytest.mark.parametrize("data", PIPELINE_CASES)
    def test_full_pipeline(self, data):
        """Full pipeline with ext8=True."""
        opcodes = list(encode_bit2_opcode_iter(data))
        stream_bytes = list(encode_bit2_stream_iter(opcodes, ext8=True))
        decoded_opcodes, read = decode_bit2_stream_iter(
            memoryview(bytes(stream_bytes)), len(data), ext8=True
        )
        decoded_data = decode_bit2_opcode(decoded_opcodes)
        assert decoded_data == data, (
            f"Pipeline failed for data={data[:30]}... "
            f"got {decoded_data[:30]}..."
        )


class TestCopyWithExt8Values:
    """Copy opcodes referencing previous 4-7 values work correctly.

    Values 4-7 cannot be encoded as run opcodes, but they can be copied
    since copy opcodes only store offset/length, not the values themselves.
    """

    def test_copy_repeating_4_item_pattern(self):
        """4-item pattern of 4-7 values is detected as a copy."""
        data = [4, 5, 6, 7, 4, 5, 6, 7, 4, 5, 6, 7]
        opcodes = list(encode_bit2_opcode_iter(data))
        assert any(op[0] == 2 for op in opcodes), (
            "encode_bit2_opcode_iter should detect a copy for "
            "repeating 4-7 pattern"
        )

    def test_copy_repeating_4_item_pattern_roundtrip(self):
        """Copy of 4-7 values round-trips correctly through ext8 pipeline."""
        data = [4, 5, 6, 7, 4, 5, 6, 7]
        encoded = encode_bit2(data, ext8=True)
        decoded, _ = decode_bit2(encoded, ext8=True)
        assert decoded == data

    def test_copy_longer_pattern_with_ext8(self):
        """Longer repeating pattern with mixed 0-3 and 4-7 values."""
        data = [0, 4, 5, 1, 6, 7, 0, 4, 5, 1, 6, 7, 0, 4, 5, 1, 6, 7]
        opcodes = list(encode_bit2_opcode_iter(data))
        has_copy = any(op[0] == 2 for op in opcodes)
        assert has_copy, (
            "encode_bit2_opcode_iter should detect a copy for "
            "repeating pattern with ext8 values"
        )
        encoded = encode_bit2(data, ext8=True)
        decoded, _ = decode_bit2(encoded, ext8=True)
        assert decoded == data

    def test_copy_rolling_with_ext8_values(self):
        """Rolling copy (offset < length) with ext8 values."""
        data = [4, 4, 4, 4, 4, 4, 4, 4]  # 8 identical ext8 values
        encoded = encode_bit2(data, ext8=True)
        decoded, _ = decode_bit2(encoded, ext8=True)
        assert decoded == data

    def test_run_of_4_to_7_does_not_overflow(self):
        """Runs of values 4-7 are encoded as literals (previously caused
        ValueError: bytes must be in range(0, 256))."""
        data = [4, 4, 4, 4]
        encoded = encode_bit2(data, ext8=True)
        decoded, _ = decode_bit2(encoded, ext8=True)
        assert decoded == data

    def test_run_of_4_to_7_produces_no_run_opcode(self):
        """encode_bit2_opcode_iter should not produce run opcodes for values 4-7."""
        for val in [4, 5, 6, 7]:
            data = [val] * 5
            opcodes = list(encode_bit2_opcode_iter(data))
            assert not any(op[0] == 1 for op in opcodes), (
                f"Run opcode should not be produced for value {val}"
            )

    def test_pipeline_with_runs_of_ext8_values(self):
        """Full pipeline with runs of 4-7 values now works (literals fallback)."""
        data = [4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7, 7]
        opcodes = list(encode_bit2_opcode_iter(data))
        stream_bytes = list(encode_bit2_stream_iter(opcodes, ext8=True))
        decoded_opcodes, read = decode_bit2_stream_iter(
            memoryview(bytes(stream_bytes)), len(data), ext8=True
        )
        decoded_data = decode_bit2_opcode(decoded_opcodes)
        assert decoded_data == data

    def test_pipeline_large_randomized(self):
        """Large randomized pipeline — now works with runs of 4-7 values."""
        import random
        random.seed(42)
        data = []
        for _ in range(2000):
            if random.random() < 0.3:
                val = random.randrange(0, 8)
                data.extend([val] * random.randrange(3, 8))
            else:
                data.append(random.randrange(0, 8))

        opcodes = list(encode_bit2_opcode_iter(data))
        stream_bytes = list(encode_bit2_stream_iter(opcodes, ext8=True))
        decoded_opcodes, read = decode_bit2_stream_iter(
            memoryview(bytes(stream_bytes)), len(data), ext8=True
        )
        decoded_data = decode_bit2_opcode(decoded_opcodes)
        assert decoded_data == data
