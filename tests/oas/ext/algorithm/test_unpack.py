import struct

import pytest

from oas.ext.algorithm.unpack import pack_little_int, unpack_little_int


class TestUnpackLittleInt:
    """Tests for unpack_little_int()."""

    # ------------------------------------------------------------------ #
    #  1-byte (uint8) tests
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("data, index, expected", [
        (b"\x00", 0, 0),
        (b"\x01", 0, 1),
        (b"\x7f", 0, 127),
        (b"\x80", 0, 128),
        (b"\xff", 0, 255),
        (b"\x00\xff", 0, 0),
        (b"\x00\xff", 1, 255),
    ])
    def test_unpack_uint8(self, data, index, expected):
        """Unpack 1-byte integers (little-endian is a single byte, so just the value)."""
        assert unpack_little_int(memoryview(data), index, 1) == expected

    # ------------------------------------------------------------------ #
    #  2-byte (uint16) tests
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("data, index, expected", [
        (b"\x00\x00", 0, 0),
        (b"\x01\x00", 0, 1),
        (b"\x00\x01", 0, 256),
        (b"\xff\xff", 0, 65535),
        (b"\x34\x12", 0, 0x1234),
        (b"\xef\xbe", 0, 0xbeef),       # 0xbeef in little-endian
        (b"\x00\x34\x12", 1, 0x1234),   # offset into data
        (b"\xff\xff\xff\xff", 0, 65535),
    ])
    def test_unpack_uint16(self, data, index, expected):
        """Unpack 2-byte little-endian integers."""
        assert unpack_little_int(memoryview(data), index, 2) == expected

    # ------------------------------------------------------------------ #
    #  3-byte (uint24) tests
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("data, index, expected", [
        (b"\x00\x00\x00", 0, 0),
        (b"\x01\x00\x00", 0, 1),
        (b"\x00\x01\x00", 0, 256),
        (b"\x00\x00\x01", 0, 65536),
        (b"\xff\xff\xff", 0, 16777215),          # 2^24 - 1
        (b"\x78\x56\x34", 0, 0x345678),          # decode 0x345678
        (b"\xef\xbe\xad", 0, 0xadbeef),          # decode 0xadbeef
        (b"\x00\x00\x00\x78\x56\x34", 3, 0x345678),  # offset
    ])
    def test_unpack_uint24(self, data, index, expected):
        """Unpack 3-byte little-endian integers (tail * 65536 + head)."""
        assert unpack_little_int(memoryview(data), index, 3) == expected

    def test_unpack_uint24_head_tail_independence(self):
        """Verify the 3-byte formula: tail * 65536 + head.

        head = first 2 bytes (little-endian uint16)
        tail = third byte
        """
        # tail=0x01, head=0x0000 => 1 * 65536 + 0 = 65536
        assert unpack_little_int(memoryview(b"\x00\x00\x01"), 0, 3) == 65536
        # tail=0x00, head=0x0001 => 0 * 65536 + 1 = 1
        assert unpack_little_int(memoryview(b"\x01\x00\x00"), 0, 3) == 1
        # tail=0x80, head=0x3412 => 128 * 65536 + 0x1234 = 8388736 + 4660 = 8393396
        assert unpack_little_int(memoryview(b"\x34\x12\x80"), 0, 3) == 128 * 65536 + 0x1234

    # ------------------------------------------------------------------ #
    #  3-byte fallback tests (fast path needs 4 bytes, fallback to 2+1)
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("data_bytes, index, expected", [
        (b"\x78\x56\x34", 0, 0x345678),          # exact 3 bytes at offset 0
        (b"\x00\x78\x56\x34", 1, 0x345678),      # exact 3 bytes at offset 1
        (b"\xff\xff\x78\x56\x34", 2, 0x345678),  # exact 3 bytes at offset 2
        (b"\x00\x00\x00", 0, 0),                 # all zeros, 3 bytes
        (b"\x01\x00\x00", 0, 1),                 # minimum non-zero, 3 bytes
        (b"\xff\xff\xff", 0, 16777215),          # max uint24, 3 bytes
    ])
    def test_uint24_fallback_exact_three_bytes(self, data_bytes, index, expected):
        """3-byte decode succeeds with exactly 3 bytes available (fallback path).

        The fast path tries to read 4 bytes as uint32 which fails;
        the fallback 2+1 method still works with exactly 3 bytes.
        """
        data = memoryview(data_bytes)
        assert unpack_little_int(data, index, 3) == expected

    @pytest.mark.parametrize("data_bytes, index", [
        (b"\x00\x00", 0),   # only 2 bytes
        (b"\x00", 0),       # only 1 byte
        (b"", 0),           # empty
        (b"\x00\x00\x00", 3),  # index past the 3-byte buffer
    ])
    def test_uint24_truncated_below_three_bytes(self, data_bytes, index):
        """3-byte decode raises ValueError when fewer than 3 bytes are available.

        Both the fast path (4-byte read) and fallback (2+1) fail.
        """
        data = memoryview(data_bytes)
        with pytest.raises(ValueError, match="Data truncated"):
            unpack_little_int(data, index, 3)

    # ------------------------------------------------------------------ #
    #  4-byte (uint32) tests
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("data, index, expected", [
        (b"\x00\x00\x00\x00", 0, 0),
        (b"\x01\x00\x00\x00", 0, 1),
        (b"\x00\x00\x00\x01", 0, 16777216),
        (b"\xff\xff\xff\xff", 0, 4294967295),        # 2^32 - 1
        (b"\xef\xbe\xad\xde", 0, 0xdeadbeef),         # 0xdeadbeef in LE
        (b"\x00" * 10 + b"\xef\xbe\xad\xde", 10, 0xdeadbeef),  # offset
    ])
    def test_unpack_uint32(self, data, index, expected):
        """Unpack 4-byte little-endian integers."""
        assert unpack_little_int(memoryview(data), index, 4) == expected

    # ------------------------------------------------------------------ #
    #  8-byte (uint64) tests
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("data, index, expected", [
        (b"\x00\x00\x00\x00\x00\x00\x00\x00", 0, 0),
        (b"\x01\x00\x00\x00\x00\x00\x00\x00", 0, 1),
        (b"\xff\xff\xff\xff\xff\xff\xff\xff", 0, 18446744073709551615),  # 2^64 - 1
        (b"\xef\xbe\xad\xde\xef\xbe\xad\xde", 0, 0xdeadbeefdeadbeef),   # repeated pattern
        (b"\x00" * 20 + b"\x01\x00\x00\x00\x00\x00\x00\x00", 20, 1),    # offset
    ])
    def test_unpack_uint64(self, data, index, expected):
        """Unpack 8-byte little-endian integers."""
        assert unpack_little_int(memoryview(data), index, 8) == expected

    # ------------------------------------------------------------------ #
    #  Input-type flexibility
    # ------------------------------------------------------------------ #

    def test_accepts_bytes_directly(self):
        """The function accepts bytes because memoryview(bytes) works."""
        result = unpack_little_int(b"\x01\x02", 0, 2)
        assert result == 0x0201

    def test_accepts_bytearray_directly(self):
        """The function accepts bytearray because memoryview(bytearray) works."""
        result = unpack_little_int(bytearray(b"\x03\x04"), 0, 2)
        assert result == 0x0403

    def test_accepts_memoryview(self):
        """The function accepts an explicit memoryview (the documented type)."""
        result = unpack_little_int(memoryview(b"\x05\x06"), 0, 2)
        assert result == 0x0605

    # ------------------------------------------------------------------ #
    #  Error cases
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("length", [0, -1, 5, 6, 7, 9, 16, 255])
    def test_invalid_length_raises(self, length):
        """Any length not in {1, 2, 3, 4, 8} must raise ValueError."""
        data = memoryview(b"\x00" * 16)
        with pytest.raises(ValueError, match="Invalid length"):
            unpack_little_int(data, 0, length)

    @pytest.mark.parametrize("data_bytes, index, length", [
        (b"", 0, 1),
        (b"\x00", 0, 2),
        (b"\x00\x00", 0, 3),
        (b"\x00\x00\x00", 0, 4),
        (b"\x00\x00\x00\x00\x00\x00\x00", 0, 8),
        (b"\x00\x00\x00\x00", 3, 2),   # not enough bytes from offset 3
        (b"\x00\x00", 1, 2),           # only 1 byte left from offset 1
        (b"\x00", 1, 1),               # index past end
    ])
    def test_truncated_data_raises(self, data_bytes, index, length):
        """When fewer bytes are available than required, raise ValueError with a truncation message."""
        data = memoryview(data_bytes)
        with pytest.raises(ValueError, match="Data truncated"):
            unpack_little_int(data, index, length)

    def test_index_out_of_range_raises(self):
        """Index beyond the buffer length should raise truncation error."""
        data = memoryview(b"\x00\x00")
        with pytest.raises(ValueError, match="Data truncated"):
            unpack_little_int(data, 5, 1)

    def test_negative_index_raises(self):
        """A negative index that wraps beyond the buffer start should raise truncation."""
        data = memoryview(b"\x00")  # single byte
        with pytest.raises(ValueError, match="Data truncated"):
            unpack_little_int(data, -2, 1)

    # ------------------------------------------------------------------ #
    #  Round trip: pack then unpack
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("value", [
        0,
        1,
        127,
        128,
        255,
    ])
    def test_round_trip_uint8(self, value):
        """Pack then unpack for 1-byte values."""
        data = memoryview(struct.pack("<B", value))
        assert unpack_little_int(data, 0, 1) == value

    @pytest.mark.parametrize("value", [
        0,
        1,
        255,
        256,
        65535,
        0x1234,
        0xABCD,
    ])
    def test_round_trip_uint16(self, value):
        """Pack then unpack for 2-byte values."""
        data = memoryview(struct.pack("<H", value))
        assert unpack_little_int(data, 0, 2) == value

    @pytest.mark.parametrize("value", [
        0,
        1,
        256,
        65536,
        16777215,  # 2^24 - 1
        0x123456,
        0xABCDEF,
    ])
    def test_round_trip_uint24(self, value):
        """Manually pack a 3-byte integer then unpack it."""
        data = bytearray(3)
        data[0] = value & 0xFF
        data[1] = (value >> 8) & 0xFF
        data[2] = (value >> 16) & 0xFF
        assert unpack_little_int(memoryview(data), 0, 3) == value

    @pytest.mark.parametrize("value", [
        0,
        1,
        65535,
        16777215,
        4294967295,  # 2^32 - 1
        0xDEADBEEF,
    ])
    def test_round_trip_uint32(self, value):
        """Pack then unpack for 4-byte values."""
        data = memoryview(struct.pack("<I", value))
        assert unpack_little_int(data, 0, 4) == value

    @pytest.mark.parametrize("value", [
        0,
        1,
        4294967295,            # 2^32 - 1
        18446744073709551615,  # 2^64 - 1
        0xDEADBEEFDEADBEEF,
    ])
    def test_round_trip_uint64(self, value):
        """Pack then unpack for 8-byte values."""
        data = memoryview(struct.pack("<Q", value))
        assert unpack_little_int(data, 0, 8) == value

    # ------------------------------------------------------------------ #
    #  Boundary / stress values
    # ------------------------------------------------------------------ #

    def test_all_uint8_values(self):
        """Verify every possible uint8 value round-trips correctly."""
        for v in range(256):
            data = memoryview(bytes([v]))
            result = unpack_little_int(data, 0, 1)
            assert result == v, f"Mismatch at uint8 value {v}"

    @pytest.mark.parametrize("length", [1, 2, 3, 4, 8])
    def test_max_value(self, length):
        """Maximum representable value for each length."""
        actual_max = (1 << (8 * length)) - 1
        # Build the little-endian bytes for the max value
        data = bytearray()
        for shift in range(0, 8 * length, 8):
            data.append((actual_max >> shift) & 0xFF)
        assert unpack_little_int(memoryview(data), 0, length) == actual_max

    def test_zero_all_lengths(self):
        """Zero should unpack to 0 regardless of length."""
        for length in (1, 2, 3, 4, 8):
            data = memoryview(b"\x00" * length)
            assert unpack_little_int(data, 0, length) == 0

    def test_partial_buffer_nonzero_start(self):
        """Verify unpacking from non-zero index within a larger buffer."""
        buf = b"\xff" * 100
        packed_42 = struct.pack("<I", 42)
        data = memoryview(buf[:50] + packed_42 + buf[54:])
        result = unpack_little_int(data, 50, 4)
        assert result == 42


class TestPackLittleInt:
    """Tests for pack_little_int()."""

    # ------------------------------------------------------------------ #
    #  Size-branch: verify output length for each range
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("value, expected_len", [
        (0, 1),
        (1, 1),
        (255, 1),
        (256, 2),
        (65535, 2),
        (65536, 3),
        (16777215, 3),           # 2^24 - 1
        (16777216, 4),
        (4294967295, 4),          # 2^32 - 1
        (4294967296, 8),
        (2**63 - 1, 8),           # 9223372036854775807 — max accepted
    ])
    def test_output_length(self, value, expected_len):
        """pack_little_int returns the correct number of bytes for each range.

        The function uses the *minimum* number of bytes needed:
          0 … 255        → 1 byte
          256 … 65535    → 2 bytes
          65536 … 16777215   → 3 bytes
          16777216 … 4294967295  → 4 bytes
          4294967296 … 2^63-1    → 8 bytes
        """
        result = pack_little_int(value)
        assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"
        assert len(result) == expected_len, (
            f"Value {value} should produce {expected_len} bytes, "
            f"got {len(result)}"
        )

    # ------------------------------------------------------------------ #
    #  Byte-exact: known output for each branch
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("value, expected_bytes", [
        (0, b"\x00"),
        (1, b"\x01"),
        (127, b"\x7f"),
        (128, b"\x80"),
        (255, b"\xff"),
    ])
    def test_uint8_values(self, value, expected_bytes):
        """Values ≤ 255 pack to a single byte (uint8)."""
        assert pack_little_int(value) == expected_bytes

    @pytest.mark.parametrize("value, expected_bytes", [
        (256, b"\x00\x01"),
        (65535, b"\xff\xff"),
        (0x1234, b"\x34\x12"),
        (0xABCD, b"\xcd\xab"),
    ])
    def test_uint16_values(self, value, expected_bytes):
        """Values in [256, 65535] pack as 2 little-endian bytes."""
        assert pack_little_int(value) == expected_bytes

    @pytest.mark.parametrize("value, expected_bytes", [
        (65536, b"\x00\x00\x01"),
        (16777215, b"\xff\xff\xff"),   # 2^24 - 1
        (0x345678, b"\x78\x56\x34"),
        (0xABCDEF, b"\xef\xcd\xab"),
    ])
    def test_uint24_values(self, value, expected_bytes):
        """Values in [65536, 16777215] pack as 3 little-endian bytes.

        The implementation packs as a uint32 then drops the leading null byte.
        """
        assert pack_little_int(value) == expected_bytes

    @pytest.mark.parametrize("value, expected_bytes", [
        (16777216, b"\x00\x00\x00\x01"),
        (4294967295, b"\xff\xff\xff\xff"),  # 2^32 - 1
        (0xDEADBEEF, b"\xef\xbe\xad\xde"),
    ])
    def test_uint32_values(self, value, expected_bytes):
        """Values in [16777216, 4294967295] pack as 4 little-endian bytes."""
        assert pack_little_int(value) == expected_bytes

    @pytest.mark.parametrize("value, expected_bytes", [
        (4294967296, b"\x00\x00\x00\x00\x01\x00\x00\x00"),
        (2**63 - 1, b"\xff\xff\xff\xff\xff\xff\xff\x7f"),  # 9223372036854775807
        (0x1234567890ABCDEF, b"\xef\xcd\xab\x90\x78\x56\x34\x12"),
    ])
    def test_uint64_values(self, value, expected_bytes):
        """Values in [4294967296, 2^63-1] pack as 8 little-endian bytes."""
        assert pack_little_int(value) == expected_bytes

    # ------------------------------------------------------------------ #
    #  Round-trip: pack then unpack (uses unpack_little_int)
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("value", [0, 1, 127, 128, 255])
    def test_round_trip_uint8(self, value):
        """pack then unpack for 1-byte values."""
        packed = pack_little_int(value)
        assert len(packed) == 1
        assert unpack_little_int(memoryview(packed), 0, 1) == value

    @pytest.mark.parametrize("value", [
        256, 65535, 0x1234, 0xABCD,
    ])
    def test_round_trip_uint16(self, value):
        """pack then unpack for 2-byte values."""
        packed = pack_little_int(value)
        assert len(packed) == 2
        assert unpack_little_int(memoryview(packed), 0, 2) == value

    @pytest.mark.parametrize("value", [
        65536, 16777215, 0x123456, 0xABCDEF,
    ])
    def test_round_trip_uint24(self, value):
        """pack then unpack for 3-byte values."""
        packed = pack_little_int(value)
        assert len(packed) == 3
        assert unpack_little_int(memoryview(packed), 0, 3) == value

    @pytest.mark.parametrize("value", [
        16777216, 4294967295, 0xDEADBEEF,
    ])
    def test_round_trip_uint32(self, value):
        """pack then unpack for 4-byte values."""
        packed = pack_little_int(value)
        assert len(packed) == 4
        assert unpack_little_int(memoryview(packed), 0, 4) == value

    @pytest.mark.parametrize("value", [
        4294967296,
        2**63 - 1,   # 9223372036854775807
        0x1234567890ABCDEF,
    ])
    def test_round_trip_uint64(self, value):
        """pack then unpack for 8-byte values."""
        packed = pack_little_int(value)
        assert len(packed) == 8
        assert unpack_little_int(memoryview(packed), 0, 8) == value

    # ------------------------------------------------------------------ #
    #  Cross-boundary: values at each threshold ±1
    # ------------------------------------------------------------------ #

    def test_boundary_255_256(self):
        """255 → 1 byte, 256 → 2 bytes."""
        assert len(pack_little_int(255)) == 1
        assert len(pack_little_int(256)) == 2

    def test_boundary_65535_65536(self):
        """65535 → 2 bytes, 65536 → 3 bytes."""
        assert len(pack_little_int(65535)) == 2
        assert len(pack_little_int(65536)) == 3

    def test_boundary_16777215_16777216(self):
        """16777215 → 3 bytes, 16777216 → 4 bytes."""
        assert len(pack_little_int(16777215)) == 3
        assert len(pack_little_int(16777216)) == 4

    def test_boundary_4294967295_4294967296(self):
        """4294967295 → 4 bytes, 4294967296 → 8 bytes."""
        assert len(pack_little_int(4294967295)) == 4
        assert len(pack_little_int(4294967296)) == 8

    # ------------------------------------------------------------------ #
    #  3-byte path: verify the UINT32_packer(data)[1:] slicing strategy
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("value", [
        0x010000,      # 65536  (smallest 3-byte value)
        0x100000,      # 1048576
        0xFFFFFF,      # 16777215 (max 3-byte value)
    ])
    def test_uint24_via_uint32_slice(self, value):
        """The 3-byte path packs as uint32 and takes the first 3 bytes.

        struct.pack('<I', value) yields 4 bytes in little-endian order:
            [LSB, byte1, byte2, MSB]
        For values < 2^24, the MSB (full_4[3]) is zero; pack_little_int
        returns full_4[:3], which drops the null MSB and keeps the
        correct 3-byte little-endian representation.
        """
        full_4 = struct.pack("<I", value)
        assert full_4[3] == 0, "MSB should be 0 for uint24 values"
        expected_3 = full_4[:3]
        assert len(expected_3) == 3
        assert pack_little_int(value) == expected_3

    # ------------------------------------------------------------------ #
    #  Error cases
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("value", [-1, -128, -2**63])
    def test_negative_value_raises(self, value):
        """Negative integers raise ValueError (unsigned packing only)."""
        with pytest.raises(ValueError, match="Value is negative"):
            pack_little_int(value)

    @pytest.mark.parametrize("value", [
        2**63,                        # 9223372036854775808 — past signed i64 max
        2**64 - 1,                    # 18446744073709551615 — max uint64
        2**64,
        2**128,
    ])
    def test_overflow_value_raises(self, value):
        """Values exceeding 2^63-1 raise ValueError."""
        with pytest.raises(ValueError, match="Value is too large"):
            pack_little_int(value)

    def test_non_integer_raises_type_error(self):
        """Non-integer types (float, str) raise TypeError from struct."""
        with pytest.raises((TypeError, struct.error)):
            pack_little_int(3.14)
        with pytest.raises((TypeError, struct.error)):
            pack_little_int("abc")
