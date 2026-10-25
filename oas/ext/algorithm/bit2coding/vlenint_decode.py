"""
Decode the vlenint format: the byte lengths of the values packed with the
bit2 format (see bit2coding_decode.py, with ext8 on, a length is 0~4), then
the values themselves in little endian, one after another.
"""
from oas.ext.algorithm.bit2coding.bit2coding_decode import decode_bit2
from oas.ext.algorithm.unpack import unpack_little_int


def decode_vlenint(data):
    """
    Decode vlenint encoded data to a list of integers.
    The number of values is read from the vint count prefix of the bit2
    section (see decode_bit2), the caller does not need to pass it in.

    Args:
        data (memoryview | bytes): vlenint encoded data

    Returns:
        tuple[list[int], int]: (decoded integers, bytes consumed)

    Raises:
        ValueError: If data is truncated or contains invalid opcodes
    """
    if isinstance(data, bytes):
        data = memoryview(data)
    byte_lengths, read = decode_bit2(data, ext8=True)
    values = []
    values_append = values.append
    for length in byte_lengths:
        if length == 0:
            values_append(0)
        else:
            # raises ValueError if the values section is truncated
            value = unpack_little_int(data, read, length)
            values_append(value)
            read += length
    return values, read
