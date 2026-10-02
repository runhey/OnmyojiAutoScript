"""
Tests for ``encode_length_int`` in bit2coding.

``encode_length_int(length)`` encodes a 0-indexed integer length into
D + variable-length bytes. D (0-3) indicates D+1 bytes follow.
"""

import pytest

from oas.ext.algorithm.bit2coding import encode_length_int
from oas.ext.algorithm.unpack import unpack_little_int


class TestEncodeLengthInt:
    """``encode_length_int(length)`` encodes an integer to (D, *bytes) in little-endian.

    The function is 0-indexed: length 0-255 uses 1 byte (D=0).
    """

    # -- D=0: 1 byte, length 0..255 -------------------------------------------

    @pytest.mark.parametrize("length, expected", [
        (0, (0, 0)),         # minimum
        (1, (0, 1)),         # 1
        (127, (0, 127)),     # 127
        (254, (0, 254)),     # 254
        (255, (0, 255)),     # max of D=0
    ])
    def test_d0(self, length, expected):
        """D=0: single byte, length ∈ [0, 255]."""
        result = encode_length_int(length)
        assert result == expected

    # -- D=1: 2 bytes, length 256..65535 --------------------------------------

    @pytest.mark.parametrize("length, expected", [
        (256, (1, 0, 1)),           # 256 LE: 0, 1
        (257, (1, 1, 1)),           # 257 LE: 1, 1
        (65534, (1, 254, 255)),     # 65534 LE: 254, 255
        (65535, (1, 255, 255)),     # 65535 LE: 255, 255
    ])
    def test_d1(self, length, expected):
        """D=1: two bytes LE, length ∈ [256, 65535]."""
        result = encode_length_int(length)
        assert result == expected

    # -- D=2: 3 bytes, length 65536..16777215 ---------------------------------

    @pytest.mark.parametrize("length, expected", [
        (65536, (2, 0, 0, 1)),          # 65536 LE: 0, 0, 1
        (65537, (2, 1, 0, 1)),          # 65537 LE: 1, 0, 1
        (16777214, (2, 254, 255, 255)),  # 16777214 LE: 254, 255, 255
        (16777215, (2, 255, 255, 255)),  # 16777215 LE: 255, 255, 255
    ])
    def test_d2(self, length, expected):
        """D=2: three bytes LE, length ∈ [65536, 16777215]."""
        result = encode_length_int(length)
        assert result == expected

    # -- D=3: 4 bytes, length 16777216..4294967295 ----------------------------

    @pytest.mark.parametrize("length, expected", [
        (16777216, (3, 0, 0, 0, 1)),          # 16777216 LE: 0, 0, 0, 1
        (16777217, (3, 1, 0, 0, 1)),          # 16777217 LE: 1, 0, 0, 1
        (4294967294, (3, 254, 255, 255, 255)),  # 4294967294 LE: 254, 255, 255, 255
        (4294967295, (3, 255, 255, 255, 255)),  # 4294967295 LE: 255, 255, 255, 255
    ])
    def test_d3(self, length, expected):
        """D=3: four bytes LE, length ∈ [16777216, 4294967295]."""
        result = encode_length_int(length)
        assert result == expected

    # -- Boundary: edge of each D range ---------------------------------------

    @pytest.mark.parametrize("length, expected", [
        (0, (0, 0)),               # absolute minimum
        (255, (0, 255)),           # max of D=0
        (256, (1, 0, 1)),          # min of D=1
        (65535, (1, 255, 255)),    # max of D=1
        (65536, (2, 0, 0, 1)),     # min of D=2
        (16777215, (2, 255, 255, 255)),  # max of D=2
        (16777216, (3, 0, 0, 0, 1)),     # min of D=3
        (4294967295, (3, 255, 255, 255, 255)),  # max of D=3
    ])
    def test_boundaries(self, length, expected):
        """Boundary values at each D transition."""
        result = encode_length_int(length)
        assert result == expected

    # -- Error: overflow ------------------------------------------------------

    def test_overflow_raises(self):
        """length > 4294967295 raises ValueError."""
        with pytest.raises(ValueError, match="Length is too large"):
            encode_length_int(4294967296)

    # -- Round-trip with unpack_little_int ------------------------------------

    @pytest.mark.parametrize("length", [
        0, 1, 2, 127, 128, 254, 255,
        256, 1000, 65534, 65535,
        65536, 100000, 16777214, 16777215,
        16777216, 1000000, 4294967294, 4294967295,
    ])
    def test_roundtrip_via_unpack(self, length):
        """encode_length_int round-trips correctly via unpack_little_int."""
        encoded = encode_length_int(length)
        d = encoded[0]
        length_bytes = bytes(encoded[1:])
        # encode_length_int stores the raw length in LE
        unpacked = unpack_little_int(memoryview(length_bytes), 0, d + 1)
        assert unpacked == length

    def test_deterministic(self):
        """Same input produces identical output."""
        for length in [0, 255, 256, 65535, 65536, 16777215, 16777216, 4294967295]:
            assert encode_length_int(length) == encode_length_int(length)
