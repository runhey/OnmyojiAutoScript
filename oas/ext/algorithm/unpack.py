import struct

from oas.ext.algorithm.const import MAX_INT64, MAX_UINT8, MAX_UINT16, MAX_UINT24, MAX_UINT32

UINT8_unpacker = struct.Struct('<B').unpack_from
UINT16_unpacker = struct.Struct('<H').unpack_from
UINT32_unpacker = struct.Struct('<I').unpack_from
UINT64_unpacker = struct.Struct('<Q').unpack_from
UINT8_packer = struct.Struct('<B').pack
UINT16_packer = struct.Struct('<H').pack
UINT32_packer = struct.Struct('<I').pack
UINT64_packer = struct.Struct('<Q').pack


def unpack_little_int(data, index, length):
    """
    Unpack a little-endian integer from data at the given index with the given length

    Args:
        data (memoryview): data to unpack
        index (int): index to unpack from
        length (int): length of the integer

    Returns:
        int: unpacked integer

    Raises:
        ValueError: If the length is invalid or data is truncated
    """
    try:
        if length == 1:
            return UINT8_unpacker(data, index)[0]
        elif length == 2:
            return UINT16_unpacker(data, index)[0]
        elif length == 3:
            try:
                # Fast path: read 4 bytes as uint32, mask to 24 bits
                return UINT32_unpacker(data, index)[0] & MAX_UINT24
            except (IndexError, struct.error):
                pass
            # Fallback: only 3 bytes available, use 2+1 method
            head = UINT16_unpacker(data, index)[0]
            tail = data[index + 2]
            return tail * 65536 + head
        elif length == 4:
            return UINT32_unpacker(data, index)[0]
        elif length == 8:
            return UINT64_unpacker(data, index)[0]
        else:
            raise ValueError(f"Invalid length: {length}")
    except (IndexError, struct.error):
        raise ValueError(
            f"Data truncated, expected {length} bytes of little-endian integer, got {len(data) - index} bytes")


def pack_little_int(data):
    if data < 0:
        raise ValueError(f"Value is negative: {data}")
    if data <= MAX_UINT8:
        return UINT8_packer(data)
    elif data <= MAX_UINT16:
        return UINT16_packer(data)
    elif data <= MAX_UINT24:
        return UINT32_packer(data)[:3]
    elif data <= MAX_UINT32:
        return UINT32_packer(data)
    elif data <= MAX_INT64:
        return UINT64_packer(data)
    else:
        raise ValueError(f"Value is too large: {data}")
