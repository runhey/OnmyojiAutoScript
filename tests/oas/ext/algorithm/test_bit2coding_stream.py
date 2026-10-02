"""
Tests for bit2coding streaming encode/decode functions.

Functions tested:
  - ``encode_bit2_stream_iter(opcodes)`` — compresses opcode tuples into uint8 bytes
  - ``decode_bit2_stream_iter(data, total)`` — decompresses bytes back to opcode tuples and byte count
"""

import struct

import pytest

from oas.ext.algorithm.bit2coding import decode_bit2_stream_iter, encode_bit2_stream_iter, encode_length_int

# ==============================================================================
# encode_bit2_stream_iter — literal opcodes
# ==============================================================================


class TestEncodeStreamLiteral:
    """Encoding literal opcodes (op_type=0)."""

    def test_one_item(self):
        """1 literal item → byte = item value (0-3)."""
        for val in range(4):
            result = list(encode_bit2_stream_iter([(0, [val])]))
            assert result == [val]

    def test_one_item_multi(self):
        """Multiple 1-item literal opcodes."""
        result = list(encode_bit2_stream_iter([(0, [0]), (0, [1]), (0, [2])]))
        assert result == [0, 1, 2]

    def test_two_items(self):
        """2 literal items → byte = 16 + first*4 + second (range 16-31)."""
        result = list(encode_bit2_stream_iter([(0, [0, 0])]))
        assert result == [16]   # 16 + 0*4+0 = 16

        result = list(encode_bit2_stream_iter([(0, [1, 2])]))
        assert result == [22]   # 16 + 1*4+2 = 22

        result = list(encode_bit2_stream_iter([(0, [3, 3])]))
        assert result == [31]   # 16 + 3*4+3 = 31

    def test_three_items_literal(self):
        """3 literal items → header 32-63 + packed bytes."""
        result = list(encode_bit2_stream_iter([(0, [1, 2, 3])]))
        # header: 29+3 = 32
        # packed: 1*64 + 2*16 + 3*4 + 0(pad) = 108
        assert result == [32, 108]

    def test_four_items_literal(self):
        """4 literal items → header + 1 packed byte."""
        result = list(encode_bit2_stream_iter([(0, [0, 1, 2, 3])]))
        # header: 29+4 = 33
        # packed: 0*64 + 1*16 + 2*4 + 3 = 27
        assert result == [33, 27]

    def test_eight_items_literal(self):
        """8 literal items → header + 2 packed bytes."""
        items = [0, 1, 2, 3, 3, 2, 1, 0]
        result = list(encode_bit2_stream_iter([(0, items)]))
        # header: 29+8 = 37
        # packed byte 1: 0*64 + 1*16 + 2*4 + 3 = 27
        # packed byte 2: 3*64 + 2*16 + 1*4 + 0 = 228
        assert result == [37, 27, 228]

    def test_thirty_two_items_literal(self):
        """32 literal items: header + 8 packed bytes."""
        items = [i % 4 for i in range(32)]
        result = list(encode_bit2_stream_iter([(0, items)]))
        assert result[0] == 61  # 29+32
        assert len(result) == 1 + 8
        for i in range(8):
            base = i * 4
            expected = items[base] * 64 + items[base + 1] * 16 + items[base + 2] * 4 + items[base + 3]
            assert result[1 + i] == expected

    def test_fifty_items_literal(self):
        """50 literal items: batch of 34 + batch of 16."""
        items = [i % 4 for i in range(50)]
        result = list(encode_bit2_stream_iter([(0, items)]))
        # batch 1: 34 items → header 63 + 9 packed bytes
        assert result[0] == 63  # 29+34
        # batch 2: 16 items → header 45 + 4 packed bytes
        assert result[10] == 45  # 29+16
        assert len(result) == 1 + 9 + 1 + 4

    def test_trailing_one_item_batch_uses_compact_format(self):
        """33 items: single batch of 33 (not 32+1)."""
        items = [i % 4 for i in range(33)]
        result = list(encode_bit2_stream_iter([(0, items)]))
        # 33 items fits in one batch: header 62 (29+33) + 9 packed bytes
        assert result[0] == 62  # 29+33
        assert len(result) == 1 + 9

    def test_trailing_two_item_batch_uses_compact_format(self):
        """34 items: single batch of 34 (not 32+2)."""
        items = [i % 4 for i in range(34)]
        result = list(encode_bit2_stream_iter([(0, items)]))
        # 34 items fits in one batch: header 63 (29+34) + 9 packed bytes
        assert result[0] == 63  # 29+34
        assert len(result) == 1 + 9

    def test_odd_padding_single_remainder(self):
        """5 items: header + 2 packed bytes (second has trailing zeros)."""
        items = [1, 2, 3, 0, 1]
        result = list(encode_bit2_stream_iter([(0, items)]))
        # header: 29+5 = 34
        assert result[0] == 34
        # [1,2,3,0] = 1*64+2*16+3*4+0 = 108
        # [1] padded = 1*64 + 0 = 64
        assert result[1] == 108
        assert result[2] == 64

    def test_odd_padding_two_remainder(self):
        """6 items: header + 2 packed bytes."""
        items = [0, 1, 2, 3, 3, 2]
        result = list(encode_bit2_stream_iter([(0, items)]))
        # header: 29+6 = 35
        assert result == [35, 27, 224]

    def test_seven_items_triple_remainder(self):
        """7 items: header + 2 packed bytes (second has 3 items)."""
        items = [1, 1, 2, 2, 3, 3, 0]
        result = list(encode_bit2_stream_iter([(0, items)]))
        # header: 29+7 = 36
        # [1,1,2,2] = 1*64+1*16+2*4+2 = 90
        # [3,3,0,pad] = 3*64+3*16+0+0 = 240
        assert result == [36, 90, 240]


# ==============================================================================
# encode_bit2_stream_iter — run opcodes
# ==============================================================================


class TestEncodeStreamRun:
    """Encoding run opcodes (op_type=1)."""

    # -- Short run: 1XXNNNNN, run length 3..34 --------------------------------

    @pytest.mark.parametrize("val, run, expected", [
        (0, 3, 128),     # 128 + 0*32 + 0
        (0, 10, 135),    # 128 + 0*32 + 7
        (0, 34, 159),    # 128 + 0*32 + 31
        (1, 3, 160),     # 128 + 1*32 + 0
        (1, 34, 191),    # 128 + 1*32 + 31
        (2, 3, 192),     # 128 + 2*32 + 0
        (2, 20, 209),    # 128 + 2*32 + 17
        (2, 34, 223),    # 128 + 2*32 + 31
        (3, 3, 224),     # 128 + 3*32 + 0
        (3, 34, 255),    # 128 + 3*32 + 31
    ])
    def test_short_run_values(self, val, run, expected):
        """Short run encoding: 128 + val*32 + (run-3)."""
        result = list(encode_bit2_stream_iter([(1, val, run)]))
        assert result == [expected]

    # -- Long run: 0110XXDD + length bytes, run >= 36 -------------------------

    def test_long_run_min(self):
        """Long run, length=35: N=0, D=0, 1 byte."""
        result = list(encode_bit2_stream_iter([(1, 0, 35)]))
        # encode_length_int(0) → (0, 0)
        # header: 96 + 0*4 + 0 = 96
        assert result == [96, 0]

    def test_long_run_val_3_len_35(self):
        """Long run, value=3, length=35."""
        result = list(encode_bit2_stream_iter([(1, 3, 35)]))
        # encode_length_int(0) → (0, 0)
        # header: 96 + 3*4 + 0 = 108 (fits in long-run range 96-111)
        assert result == [108, 0]

    def test_long_run_len_290(self):
        """Long run, length=290: N=255, D=0, 1 byte."""
        result = list(encode_bit2_stream_iter([(1, 1, 290)]))
        # encode_length_int(255) → (0, 255)
        # header: 96 + 1*4 + 0 = 100
        assert result == [100, 255]

    def test_long_run_len_291(self):
        """Long run, length=291: N=256, D=1, 2 bytes LE."""
        result = list(encode_bit2_stream_iter([(1, 2, 291)]))
        # encode_length_int(256) → (1, 0, 1)
        # header: 96 + 2*4 + 1 = 105
        assert result == [105, 0, 1]

    def test_long_run_large(self):
        """Long run with large length."""
        length = 100000
        result = list(encode_bit2_stream_iter([(1, 0, length)]))
        d, *length_bytes = encode_length_int(length - 35)
        expected = [96 + 0 * 4 + d] + length_bytes
        assert result == expected

    def test_long_run_max(self):
        """Long run at 2^32 boundary."""
        length = 4294967296
        result = list(encode_bit2_stream_iter([(1, 3, length)]))
        d, *length_bytes = encode_length_int(length - 35)
        expected = [96 + 3 * 4 + d] + length_bytes
        assert result == expected

    def test_short_run_boundary(self):
        """Boundary at run=34 (max short) and run=35 (min long)."""
        short = list(encode_bit2_stream_iter([(1, 0, 34)]))
        assert short == [159]  # 128 + 0 + 31

        long_v = list(encode_bit2_stream_iter([(1, 0, 35)]))
        assert long_v[0] == 96  # long run header

    def test_all_values_long_run_d0(self):
        """All 4 values with D=0 produce unique long-run headers."""
        for val in range(4):
            result = list(encode_bit2_stream_iter([(1, val, 35)]))
            # header: 96 + val*4 + 0, all in range 96-111
            expected_header = 96 + val * 4
            assert expected_header < 112, f"val={val} header should be <112"
            assert result[0] == expected_header
            assert result[1] == 0  # N=0


# ==============================================================================
# encode_bit2_stream_iter — copy opcodes
# ==============================================================================


class TestEncodeStreamCopy:
    """Encoding copy opcodes (op_type=2)."""

    # -- Short copy: 010LLLLL + offset byte, length 1..32, offset 1..256 -----

    @pytest.mark.parametrize("offset, length, expected", [
        (1, 1, [64, 0]),       # 63+1=64, offset-1=0
        (1, 32, [95, 0]),      # 63+32=95, offset-1=0
        (256, 1, [64, 255]),   # 63+1=64, offset-1=255
        (256, 32, [95, 255]),  # 63+32=95, offset-1=255
        (100, 15, [78, 99]),   # 63+15=78, offset-1=99
    ])
    def test_short_copy_values(self, offset, length, expected):
        """Various short copy encodings."""
        result = list(encode_bit2_stream_iter([(2, offset, length)]))
        assert result == expected

    def test_short_copy_boundary(self):
        """Boundary: offset=256 (max), length=32 (max)."""
        result = list(encode_bit2_stream_iter([(2, 256, 32)]))
        assert result == [95, 255]

    # -- Long copy: 0111LLFF + length bytes + offset bytes -------------------

    def test_long_copy_min(self):
        """Long copy with length=1, offset=1: D=0 for both, 1 byte each."""
        result = list(encode_bit2_stream_iter([(2, 1, 1)]))
        # encoded as short copy since length<=32 and offset<=256
        assert result == [64, 0]

    def test_long_copy_used_when_offset_exceeds_256(self):
        """Long copy triggered when offset > 256."""
        result = list(encode_bit2_stream_iter([(2, 257, 1)]))
        # encode_length_int(1-1)=encode_length_int(0) → (0, 0)
        # encode_length_int(257-1)=encode_length_int(256) → (1, 0, 1)
        # header: 112 + 0*16 + 1 = 113
        assert result == [113, 0, 0, 1]

    def test_long_copy_used_when_length_exceeds_32(self):
        """Long copy triggered when length > 32."""
        result = list(encode_bit2_stream_iter([(2, 1, 33)]))
        # encode_length_int(33-1)=encode_length_int(32) → (0, 32)
        # encode_length_int(1-1)=encode_length_int(0) → (0, 0)
        # header: 112 + 0*16 + 0 = 112
        assert result == [112, 32, 0]

    def test_long_copy_large_length(self):
        """Long copy with length requiring D=1 (2 bytes)."""
        result = list(encode_bit2_stream_iter([(2, 1, 300)]))
        l_d, *l_bytes = encode_length_int(300 - 1)
        f_d, *f_bytes = encode_length_int(1 - 1)
        expected = [112 + l_d * 4 + f_d] + l_bytes + f_bytes
        assert result == expected

    def test_long_copy_large_offset(self):
        """Long copy with offset requiring D=1 (2 bytes)."""
        result = list(encode_bit2_stream_iter([(2, 500, 1)]))
        l_d, *l_bytes = encode_length_int(1 - 1)
        f_d, *f_bytes = encode_length_int(500 - 1)
        expected = [112 + l_d * 4 + f_d] + l_bytes + f_bytes
        assert result == expected

    def test_long_copy_both_large(self):
        """Long copy with both length and offset large."""
        result = list(encode_bit2_stream_iter([(2, 1000, 500)]))
        l_d, *l_bytes = encode_length_int(500 - 1)
        f_d, *f_bytes = encode_length_int(1000 - 1)
        expected = [112 + l_d * 4 + f_d] + l_bytes + f_bytes
        assert result == expected

    def test_long_copy_various_d_combos(self):
        """Long copy with different D combinations."""
        for offset, length in [(300, 1), (1, 300), (65536, 1), (1, 65536)]:
            result = list(encode_bit2_stream_iter([(2, offset, length)]))
            l_d, *l_bytes = encode_length_int(length - 1)
            f_d, *f_bytes = encode_length_int(offset - 1)
            expected = [112 + l_d * 4 + f_d] + l_bytes + f_bytes
            assert result == expected


# ==============================================================================
# encode_bit2_stream_iter — mixed opcodes and edge cases
# ==============================================================================


class TestEncodeStreamMixed:
    """Mixed opcodes and edge cases."""

    def test_empty_opcodes(self):
        """Empty opcode list yields no bytes."""
        result = list(encode_bit2_stream_iter([]))
        assert result == []

    def test_mixed_sequence(self):
        """Sequence with all three opcode types."""
        opcodes = [
            (0, [0]),        # 1-item literal → [0]
            (1, 2, 5),       # short run → 128 + 2*32 + 2 = 194
            (2, 10, 3),      # short copy → [63+3=66, 10-1=9]
        ]
        result = list(encode_bit2_stream_iter(opcodes))
        assert result == [0, 194, 66, 9]

    def test_invalid_opcode_type(self):
        """Invalid opcode type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid opcode"):
            list(encode_bit2_stream_iter([(99, None)]))

    def test_deterministic(self):
        """Same input produces identical output."""
        opcodes = [(0, [1, 2, 3]), (1, 0, 7), (2, 5, 2)]
        assert list(encode_bit2_stream_iter(opcodes)) == list(encode_bit2_stream_iter(opcodes))


# ==============================================================================
# decode_bit2_stream_iter — individual opcode decoding
# ==============================================================================


class TestDecodeStreamOneItemLiteral:
    """Decoding 1-item literal (byte 0-15 → opcode (0, [val]))."""

    @pytest.mark.parametrize("val", range(4))
    def test_one_item(self, val):
        """Bytes 0-3 decode as 1-item literal."""
        data = memoryview(bytes([val]))
        opcodes, read = decode_bit2_stream_iter(data, 1)
        assert opcodes == [(0, [val])]
        assert read == 1

    def test_bytes_4_to_15_invalid(self):
        """Bytes 4-15 are outside valid 2-bit value range → ValueError."""
        for byte in [4, 7, 15]:
            data = memoryview(bytes([byte]))
            with pytest.raises(ValueError, match="Invalid opcode"):
                decode_bit2_stream_iter(data, 1)


class TestDecodeStreamTwoItemLiteral:
    """Decoding 2-item literal (byte 16-31 → opcode (0, [first, second]))."""

    @pytest.mark.parametrize("byte, expected", [
        (16, [0, 0]),   # 00010000 → first=0, second=0
        (17, [0, 1]),   # 00010001 → first=0, second=1
        (19, [0, 3]),   # 00010011 → first=0, second=3
        (20, [1, 0]),   # 00010100 → first=1, second=0
        (22, [1, 2]),   # 00010110 → first=1, second=2
        (31, [3, 3]),   # 00011111 → first=3, second=3
    ])
    def test_two_item_literal(self, byte, expected):
        """Byte 16-31 decodes to two literal values."""
        data = memoryview(bytes([byte]))
        opcodes, read = decode_bit2_stream_iter(data, 2)
        assert opcodes == [(0, expected)]
        assert read == 1


class TestDecodeStreamBatchLiteral:
    """Decoding batch literal (byte 32-63 → 3-34 items)."""

    def test_three_items(self):
        """Batch of 3 items: byte 32 + 1 packed byte with trailing zeros."""
        data = memoryview(bytes([32, 108]))  # 29+3, packed: 1*64+2*16+3*4 = 108
        opcodes, read = decode_bit2_stream_iter(data, 3)
        assert opcodes == [(0, [1, 2, 3])]
        assert read == 2

    def test_four_items(self):
        """Batch of 4 items: byte 33 + 1 packed byte."""
        data = memoryview(bytes([33, 27]))  # 29+4, packed: 0*64+1*16+2*4+3 = 27
        opcodes, read = decode_bit2_stream_iter(data, 4)
        assert opcodes == [(0, [0, 1, 2, 3])]
        assert read == 2

    def test_eight_items(self):
        """Batch of 8 items: byte 37 + 2 packed bytes."""
        data = memoryview(bytes([37, 27, 228]))
        opcodes, read = decode_bit2_stream_iter(data, 8)
        assert opcodes == [(0, [0, 1, 2, 3, 3, 2, 1, 0])]
        assert read == 3

    def test_thirty_two_items(self):
        """Batch of 32 items: byte 61 + 8 packed bytes."""
        expected_items = [i % 4 for i in range(32)]
        packed = bytearray()
        for i in range(0, 32, 4):
            packed.append(expected_items[i] * 64 + expected_items[i + 1] * 16 + expected_items[i + 2] * 4 + expected_items[i + 3])
        data = memoryview(bytes([61]) + packed)
        opcodes, read = decode_bit2_stream_iter(data, 32)
        assert opcodes == [(0, expected_items)]
        assert read == 9

    def test_two_items_trailing_one(self):
        """5 items: should use batch header for all 5, not split (n!=1 or 2 in encode's batched loop)."""
        # encode_bit2_stream_iter produces batches via batched(items, 34)
        # 5 items is < 34 so it's one batch → byte 34 + 2 packed bytes
        data = memoryview(bytes([34, 108, 64]))  # 29+5, [1,2,3,0]=108, [1,pad]=64
        opcodes, read = decode_bit2_stream_iter(data, 5)
        assert opcodes == [(0, [1, 2, 3, 0, 1])]
        assert read == 3


class TestDecodeStreamShortRun:
    """Decoding short run (byte 128-255 → run)."""

    @pytest.mark.parametrize("byte, expected_val, expected_run", [
        (128, 0, 3),
        (129, 0, 4),
        (159, 0, 34),
        (160, 1, 3),
        (191, 1, 34),
        (192, 2, 3),
        (208, 2, 19),
        (224, 3, 3),
        (255, 3, 34),
    ])
    def test_short_run(self, byte, expected_val, expected_run):
        """Short run decoding."""
        data = memoryview(bytes([byte]))
        opcodes, read = decode_bit2_stream_iter(data, expected_run)
        assert opcodes == [(1, expected_val, expected_run)]
        assert read == 1


class TestDecodeStreamLongRun:
    """Decoding long run (byte 96-111 → run with length bytes)."""

    def test_long_run_min(self):
        """Long run, D=0, N=0 → run=35."""
        data = memoryview(bytes([96, 0]))
        opcodes, read = decode_bit2_stream_iter(data, 35)
        assert opcodes == [(1, 0, 35)]
        assert read == 2

    def test_long_run_val_nibble(self):
        """Long run: 0110 XX DD format, XX at bits 3-2, all 4 values work."""
        for val in range(4):
            byte = 96 + val * 4  # D=0
            data = memoryview(bytes([byte, 0]))
            opcodes, read = decode_bit2_stream_iter(data, 35)
            assert opcodes == [(1, val, 35)]
            assert read == 2

    def test_long_run_n_255(self):
        """Long run, N=255, D=0 → run=290."""
        data = memoryview(bytes([96, 255]))
        opcodes, read = decode_bit2_stream_iter(data, 290)
        assert opcodes == [(1, 0, 290)]
        assert read == 2

    def test_long_run_n_256(self):
        """Long run, N=256, D=1, 2 bytes LE → run=291."""
        data = memoryview(bytes([97, 0, 1]))
        opcodes, read = decode_bit2_stream_iter(data, 291)
        assert opcodes == [(1, 0, 291)]
        assert read == 3

    def test_long_run_n_65535(self):
        """Long run, N=65535, D=1, 2 bytes LE → run=65570."""
        data = memoryview(bytes([97, 255, 255]))
        opcodes, read = decode_bit2_stream_iter(data, 65570)
        assert opcodes == [(1, 0, 65570)]
        assert read == 3

    def test_long_run_n_65536(self):
        """Long run, N=65536, D=2, 3 bytes LE → run=65571."""
        d_bytes = struct.pack('<I', 65536)[:3]
        data = memoryview(bytes([98]) + d_bytes)
        opcodes, read = decode_bit2_stream_iter(data, 65571)
        assert opcodes == [(1, 0, 65571)]
        assert read == 4

    def test_long_run_n_100000(self):
        """Long run, N=100000, D=2, 3 bytes LE."""
        d_bytes = struct.pack('<I', 100000)[:3]
        data = memoryview(bytes([98]) + d_bytes)
        opcodes, read = decode_bit2_stream_iter(data, 100035)
        assert opcodes == [(1, 0, 100035)]
        assert read == 4

    def test_long_run_d3(self):
        """Long run, D=3, 4 bytes LE."""
        n = 1000000
        d_bytes = struct.pack('<I', n)
        data = memoryview(bytes([99]) + d_bytes)
        opcodes, read = decode_bit2_stream_iter(data, n + 35)
        assert opcodes == [(1, 0, n + 35)]
        assert read == 5


class TestDecodeStreamShortCopy:
    """Decoding short copy (byte 64-95 → copy with offset byte)."""

    @pytest.mark.parametrize("byte, off_byte, expected_offset, expected_len", [
        (64, 0, 1, 1),
        (64, 255, 256, 1),
        (95, 0, 1, 32),
        (95, 255, 256, 32),
        (78, 99, 100, 15),
    ])
    def test_short_copy(self, byte, off_byte, expected_offset, expected_len):
        """Short copy decoding."""
        data = memoryview(bytes([byte, off_byte]))
        opcodes, read = decode_bit2_stream_iter(data, expected_len)
        assert opcodes == [(2, expected_offset, expected_len)]
        assert read == 2


class TestDecodeStreamLongCopy:
    """Decoding long copy (byte 112-127 → copy with extra length/offset bytes)."""

    def test_long_copy_min(self):
        """Long copy, L=0, F=0, 1 byte each → length=1, offset=1."""
        data = memoryview(bytes([112, 0, 0]))
        opcodes, read = decode_bit2_stream_iter(data, 1)
        assert opcodes == [(2, 1, 1)]
        assert read == 3

    def test_long_copy_larger_values(self):
        """Long copy with non-trivial length and offset."""
        # encode: (2, 100, 50)
        # length-1=49 → D=0, offset-1=99 → D=0
        # header: 112 + 0*16 + 0 = 112
        # bytes: [112, 49, 99]
        data = memoryview(bytes([112, 49, 99]))
        opcodes, read = decode_bit2_stream_iter(data, 50)
        assert opcodes == [(2, 100, 50)]
        assert read == 3

    def test_long_copy_with_offset_d1(self):
        """Long copy with offset needing 2 bytes D=1."""
        # offset=300, length=1: offset-1=299 → D=1 (2 bytes)
        # encode: (2, 300, 1)
        # header: 112 + 0*16 + 1 = 113
        # bytes: [113, 0, 43, 1] (length=0, offset=299 LE=43,1)
        data = memoryview(bytes([113, 0, 43, 1]))
        opcodes, read = decode_bit2_stream_iter(data, 1)
        assert opcodes == [(2, 300, 1)]
        assert read == 4

    def test_long_copy_both_d1(self):
        """Long copy with both length and offset needing 2 bytes D=1."""
        # length=300 (len-1=299 → D=1), offset=500 (off-1=499 → D=1)
        l_bytes = struct.pack('<H', 299)
        f_bytes = struct.pack('<H', 499)
        data = memoryview(bytes([112 + 1 * 4 + 1]) + l_bytes + f_bytes)
        opcodes, read = decode_bit2_stream_iter(data, 300)
        assert opcodes == [(2, 500, 300)]
        assert read == 5

    def test_long_copy_varied_nibbles(self):
        """All 4 nibble combinations for L and F."""
        for l_d in range(4):
            for f_d in range(4):
                byte = 112 + l_d * 4 + f_d
                # length=1 (len-1=0 → D=0 regardless), offset=1
                # But the decode reads l_d+1 and f_d+1 bytes
                l_bytes_needed = l_d + 1
                f_bytes_needed = f_d + 1
                l_bytes = bytes([0]) * l_bytes_needed
                f_bytes = bytes([0]) * f_bytes_needed
                data = memoryview(bytes([byte]) + l_bytes + f_bytes)
                opcodes, read = decode_bit2_stream_iter(data, 1)
                assert opcodes == [(2, 1, 1)], f"Failed l_d={l_d}, f_d={f_d}"
                assert read == 1 + l_bytes_needed + f_bytes_needed


class TestDecodeStreamInvalid:
    """Invalid inputs."""

    def test_truncated_data(self):
        """Empty data raises ValueError."""
        data = memoryview(bytes([]))
        with pytest.raises(ValueError, match="Data truncated"):
            decode_bit2_stream_iter(data, 1)

    def test_truncated_short_copy_missing_offset(self):
        """Short copy missing offset raises ValueError."""
        data = memoryview(bytes([64]))
        with pytest.raises(ValueError, match="Data truncated"):
            decode_bit2_stream_iter(data, 1)

    def test_truncated_batch_missing_items(self):
        """Batch literal missing its packed bytes raises ValueError."""
        # byte 32 declares a batch of 3 items, carried by 1 packed byte
        data = memoryview(bytes([32]))
        with pytest.raises(ValueError, match="Data truncated"):
            decode_bit2_stream_iter(data, 3)

    def test_truncated_batch_partial_items(self):
        """Batch literal with fewer packed bytes than it declares raises ValueError."""
        # byte 63 declares a batch of 34 items, carried by 9 packed bytes
        data = memoryview(bytes([63, 1, 2]))
        with pytest.raises(ValueError, match="Data truncated"):
            decode_bit2_stream_iter(data, 34)

    def test_truncated_long_copy_missing_bytes(self):
        """Long copy missing length/offset bytes raises ValueError."""
        data = memoryview(bytes([112]))  # L_d=0, F_d=0, needs 2 more bytes
        with pytest.raises(ValueError):
            decode_bit2_stream_iter(data, 1)

        data = memoryview(bytes([113]))  # L_d=0, F_d=1, needs 3 more bytes
        with pytest.raises(ValueError):
            decode_bit2_stream_iter(data, 1)

    @pytest.mark.parametrize("opcodes, total", [
        ([(0, [i % 4 for i in range(34)])], 34),  # batch literal
        ([(1, 2, 100)], 100),                   # long run
        ([(2, 10, 3)], 3),                      # short copy
        ([(2, 300, 40)], 40),                   # long copy
        ([(0, [0]), (1, 2, 5), (2, 10, 3)], 9),  # mixed
    ])
    def test_any_truncation_raises_value_error(self, opcodes, total):
        """A truncated stream must raise ValueError, never another exception.

        The opcode bytes are read in several branches, a stream that ends
        inside one of them is a truncated stream, not an IndexError.
        """
        encoded = bytes(encode_bit2_stream_iter(opcodes))
        assert len(encoded) > 1
        for end in range(len(encoded)):
            try:
                decoded, read = decode_bit2_stream_iter(memoryview(encoded[:end]), total)
            except ValueError:
                continue
            except Exception as e:
                raise AssertionError(
                    f"truncate at {end}: raised {type(e).__name__}: {e}") from e
            # a truncated stream that decodes must have carried enough values
            count = sum(len(opcode[1]) if opcode[0] == 0 else opcode[2] for opcode in decoded)
            assert count >= total, f"truncate at {end}: decoded {count} values, total {total}"
            assert read <= end


# ==============================================================================
# decode_bit2_stream_iter — mixed and boundary
# ==============================================================================


class TestDecodeStreamMixed:
    """Multiple sequential opcodes."""

    def test_two_single_literals(self):
        """Two consecutive 1-item literals."""
        data = memoryview(bytes([0, 1]))
        opcodes, read = decode_bit2_stream_iter(data, 2)
        assert opcodes == [(0, [0]), (0, [1])]
        assert read == 2

    def test_literal_then_run(self):
        """Literal then run."""
        data = memoryview(bytes([0, 128]))
        opcodes, read = decode_bit2_stream_iter(data, 4)
        assert opcodes == [(0, [0]), (1, 0, 3)]
        assert read == 2

    def test_run_then_copy(self):
        """Run then short copy."""
        data = memoryview(bytes([160, 64, 0]))
        opcodes, read = decode_bit2_stream_iter(data, 4)
        assert opcodes == [(1, 1, 3), (2, 1, 1)]
        assert read == 3

    def test_all_three_types_via_encode(self):
        """Encode then decode all three opcode types."""
        opcodes = [(0, [0]), (1, 2, 4), (2, 3, 2)]
        encoded = list(encode_bit2_stream_iter(opcodes))
        total = 1 + 4 + 2
        decoded, read = decode_bit2_stream_iter(memoryview(bytes(encoded)), total)
        assert decoded == opcodes
        assert read == len(encoded)


class TestDecodeStreamTotal:
    """Correct handling of the ``total`` parameter."""

    def test_stop_at_total_exact(self):
        """Decoding stops when count reaches total exactly."""
        data = memoryview(bytes([128, 160]))
        opcodes, read = decode_bit2_stream_iter(data, 6)
        assert opcodes == [(1, 0, 3), (1, 1, 3)]
        assert read == 2

    def test_stop_at_total_partial(self):
        """Decoding stops mid-stream when total reached."""
        data = memoryview(bytes([128, 160]))
        opcodes, read = decode_bit2_stream_iter(data, 3)
        assert opcodes == [(1, 0, 3)]
        assert read == 1

    def test_total_exceeds_available(self):
        """If total > available data, decoder raises ValueError."""
        data = memoryview(bytes([128]))
        with pytest.raises(ValueError, match="Data truncated"):
            decode_bit2_stream_iter(data, 10)


# ==============================================================================
# Round-trip tests — encode_bit2_stream_iter then decode_bit2_stream_iter
# ==============================================================================

# Build a comprehensive set of roundtrippable opcodes
def _build_roundtrip_cases():
    cases = []
    # 1-item literals
    for v in range(4):
        cases.append([(0, [v])])
    # 2-item literals
    cases.append([(0, [0, 1])])
    cases.append([(0, [3, 2])])
    # Batch literals (3-32 items)
    cases.append([(0, [0, 1, 2])])
    cases.append([(0, [1, 2, 3, 0])])
    cases.append([(0, [i % 4 for i in range(7)])])
    cases.append([(0, [i % 4 for i in range(32)])])
    # Batch of 33 items (single batch with new 3-34 range)
    cases.append([(0, [i % 4 for i in range(33)])])
    # Short runs
    for v in range(4):
        cases.append([(1, v, 4)])
        cases.append([(1, v, 20)])
        cases.append([(1, v, 34)])
    # Long runs
    cases.append([(1, 0, 35)])
    cases.append([(1, 1, 100)])
    cases.append([(1, 2, 291)])
    cases.append([(1, 3, 1000)])
    cases.append([(1, 0, 100000)])
    # Short copies
    cases.append([(2, 1, 1)])
    cases.append([(2, 100, 15)])
    cases.append([(2, 256, 32)])
    cases.append([(2, 50, 5)])
    # Long copies
    cases.append([(2, 1, 33)])
    cases.append([(2, 257, 1)])
    cases.append([(2, 500, 300)])
    cases.append([(2, 1000, 50)])
    # Mixed sequences
    cases.append([(0, [0]), (1, 0, 4)])
    cases.append([(1, 0, 4), (0, [1])])
    cases.append([(1, 0, 4), (2, 3, 2)])
    cases.append([(0, [0]), (1, 1, 5), (2, 3, 2)])
    cases.append([(0, [0, 1, 2]), (1, 3, 10), (2, 256, 32)])
    cases.append([(0, [i % 4 for i in range(33)]), (1, 1, 6), (2, 200, 10)])
    return cases


class TestRoundtripStream:
    """Round-trip encode→decode for all opcode types."""

    ROUNDTRIP_OPCODES = _build_roundtrip_cases()

    @staticmethod
    def _merge_consecutive_literals(opcodes):
        """Merge consecutive literal opcodes into one (the stream encoder may split large literals)."""
        if not opcodes:
            return opcodes
        merged = []
        for op in opcodes:
            if op[0] == 0 and merged and merged[-1][0] == 0:
                # Merge with previous literal
                prev = merged.pop()
                merged.append((0, prev[1] + op[1]))
            else:
                merged.append(op)
        return merged

    @pytest.mark.parametrize("opcodes", ROUNDTRIP_OPCODES)
    def test_roundtrip(self, opcodes):
        """decode(encode(opcodes)) == opcodes (consecutive literals merged)."""
        encoded = list(encode_bit2_stream_iter(opcodes))
        total = sum(
            op[2] if op[0] != 0 else len(op[1])
            for op in opcodes
        )
        decoded, read = decode_bit2_stream_iter(memoryview(bytes(encoded)), total)
        # Merge consecutive literals since the stream encoder may split them
        merged_decoded = self._merge_consecutive_literals(decoded)
        assert merged_decoded == opcodes, f"Failed for {opcodes}"
        assert read == len(encoded)

    def test_deterministic(self):
        """Same input produces identical output."""
        opcodes = [(0, [0]), (1, 2, 10), (2, 50, 5)]
        assert list(encode_bit2_stream_iter(opcodes)) == list(encode_bit2_stream_iter(opcodes))

    def test_roundtrip_large_sequence(self):
        """Large mixed sequence round-trips correctly."""
        opcodes = []
        total = 0
        for i in range(100):
            if i % 3 == 0:
                opcodes.append((0, [i % 4]))
                total += 1
            elif i % 3 == 1:
                opcodes.append((1, i % 4, 6))
                total += 6
            else:
                opcodes.append((2, (i % 10) + 1, 7))
                total += 7
        encoded = list(encode_bit2_stream_iter(opcodes))
        decoded, read = decode_bit2_stream_iter(memoryview(bytes(encoded)), total)
        assert decoded == opcodes
        assert read == len(encoded)

    def test_many_one_item_literals(self):
        """1000 1-item literals."""
        n = 1000
        opcodes = [(0, [i % 4]) for i in range(n)]
        encoded = list(encode_bit2_stream_iter(opcodes))
        decoded, read = decode_bit2_stream_iter(memoryview(bytes(encoded)), n)
        assert decoded == opcodes
        assert read == len(encoded)

    def test_decode_byte_count(self):
        """Decode returns correct consumed byte count."""
        opcodes = [(0, [0]), (1, 1, 5), (2, 3, 2)]
        encoded = list(encode_bit2_stream_iter(opcodes))
        total = 1 + 5 + 2
        data = memoryview(bytes(encoded))
        decoded, read = decode_bit2_stream_iter(data, total)
        assert read == len(encoded)
        assert decoded == opcodes

    def test_partial_decode(self):
        """Partial decode stops correctly."""
        opcodes = [(0, [0]), (1, 1, 5)]
        encoded = list(encode_bit2_stream_iter(opcodes))
        data = memoryview(bytes(encoded))
        decoded, read = decode_bit2_stream_iter(data[:1], 1)
        assert decoded == [(0, [0])]
        assert read == 1


# ==============================================================================
# Integration test — full data pipeline
# ==============================================================================


class TestFullPipeline:
    """End-to-end: data → encode_bit2_opcode_iter → encode_bit2_stream_iter
    → decode_bit2_stream_iter → decode_bit2_opcode → original data.
    """

    PIPELINE_CASES = [
        [],
        [0],
        [1],
        [3],
        [0, 1],
        [0, 1, 2, 3],
        [0, 0, 0, 0],
        [1] * 5,
        [2] * 10,
        [3] * 35,
        [0, 0, 0, 0, 1, 1, 1, 1],
        [0, 1, 2, 3, 0, 1, 2, 3],
        [0, 1] * 10,
        [1, 2, 3] * 5,
        [i % 4 for i in range(50)],
        [i % 4 for i in range(100)],
        [i % 4 for i in range(500)],
    ]

    @pytest.mark.parametrize("data", PIPELINE_CASES)
    def test_full_pipeline(self, data):
        """Full encode → stream encode → stream decode → opcode decode."""
        from oas.ext.algorithm.bit2coding import decode_bit2_opcode, encode_bit2_opcode_iter

        opcodes = list(encode_bit2_opcode_iter(data))
        stream_bytes = list(encode_bit2_stream_iter(opcodes))
        decoded_opcodes, read = decode_bit2_stream_iter(
            memoryview(bytes(stream_bytes)), len(data)
        )
        decoded_data = decode_bit2_opcode(decoded_opcodes)
        assert decoded_data == data, (
            f"Pipeline failed for data={data[:30]}... "
            f"got {decoded_data[:30]}..."
        )
