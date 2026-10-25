"""
The pure Python encoder of the vlenint format, the reference of the C
encoder of vlenint_encode_c.py.
"""
from collections import deque

from oas.ext.algorithm.bit2coding.bit2coding_encode_python import encode_bit2
from oas.ext.algorithm.const import MAX_UINT32
from oas.ext.algorithm.unpack import pack_little_int


def vlenint_value_check(data):
    """
    Check if the values in data are valid for vlenint encoding

    Args:
        data (Iterable[int]): list of values to encode

    Raises:
        ValueError: if any value is negative
    """
    if not data:
        return
    min_val = min(data)
    max_val = max(data)
    if min_val < 0:
        raise ValueError(f"[encode_vlenint] Value must be >= 0, got {min_val}")
    if max_val > MAX_UINT32:
        raise ValueError(f"[encode_vlenint] Value must be < 2**32, got {max_val}")


def encode_vlenint(data):
    """
    Encode numbers to variable length int. vlenint have 2 sections
    [byte_length]: bytes length of each value compressed in bit2coding
        byte_length indicates the bytes length of each value in the following section
        value=0 -> byte_length=0
        value=1..255 -> byte_length=1
        value=256..65535 -> byte_length=2
        value=65536..16777215 -> byte_length=3
        value=16777216..4294967295 -> byte_length=4
    [values]: values in little-endian

    bit2coding adds a vint count prefix of its own (see encode_bit2), so
    the number of values is stored once, not twice. decode_vlenint reads
    the count from the bit2 prefix and does not need external input.

    Args:
        data (Iterable[int]): list of values to encode

    Returns:
        bytes: vlenint encoded data
    """
    data = list(data)
    vlenint_value_check(data)
    lengths = deque()
    value_bytes = deque()
    for item in data:
        if item == 0:
            lengths.append(0)
        else:
            packed = pack_little_int(item)
            lengths.append(len(packed))
            value_bytes.append(packed)

    section_lengths = encode_bit2(lengths, ext8=True)
    section_values = b''.join(value_bytes)
    return b''.join([section_lengths, section_values])
