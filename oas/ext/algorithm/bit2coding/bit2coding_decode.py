"""
Decode bit2 format data.

The decoder is the reference of the format: it reads back what both the
Python encoder (bit2coding_encode_python.py) and the C encoder
(bit2coding_encode_c.py) write, the encoding side may change its parse,
the decoding side may not.
"""
from oas.ext.algorithm.unpack import unpack_little_int
from oas.ext.algorithm.vint import decode_vint


def decode_bit2_opcode(opcodes):
    """
    将操作元组列表重新解码为原始的 list[int]

    Args:
        opcodes (Iterable[tuple])

    Returns:
        list[int]: list of 2 bits value, value must be 0, 1, 2, 3
    """
    res = []

    for opcode in opcodes:
        op_type = opcode[0]

        if op_type == 0:
            # 0: literal values (list[int])
            res.extend(opcode[1])

        elif op_type == 1:
            # 1: run value and length
            _, run_val, run_len = opcode
            res.extend([run_val] * run_len)

        elif op_type == 2:
            # 2: copy offset and length
            _, offset, length = opcode
            start = len(res) - offset

            if length <= offset:
                # 普通复制，直接切片
                res.extend(res[start: start + length])
            else:
                # 滚动复制 (Rolling Copy)，例如 offset=1, length=5
                # 利用切片乘法避免 Python 层的 for 循环
                pattern = res[start: start + offset]
                repeats = length // offset
                remainder = length % offset
                res.extend(pattern * repeats + pattern[:remainder])

    return res


def decode_bit2_stream_iter(data, total, ext8=False):
    """
    Decode compressed operations to opcodes list
    See encode_bit2_stream_iter for more information

    Args:
        data (memoryview): compressed data
        total (int): Total numbers
        ext8 (bool): True to enable ext8 support to allow 4/5/6/7 as literal values

    Returns:
        tuple[list[int], int]: (list of opcodes, read bytes count)

    Raises:
        ValueError: If the stream ends before ``total`` numbers are
            decoded, or an opcode is invalid
    """
    count = 0
    read = 0
    opcodes = []
    if total == 0:
        return opcodes, read
    while True:
        try:
            byte = data[read]
        except IndexError:
            raise ValueError(f"[decode_bit2] Data truncated, expected {total} numbers, got {count}")
        read += 1
        # 1XXNNNNN: run XX for N+3 times, N (0~31)
        if byte >= 128:
            item = (byte // 32) % 4
            run = (byte % 32) + 3
            opcodes.append((1, item, run))
            count += run
        # 0111LLFF: copy offset and length
        #           L (0~3) indicates to read L+1 bytes, F (0~3) indicates to read F+1 bytes
        elif byte >= 112:
            l_d = (byte % 16) // 4
            f_d = byte % 4
            length = unpack_little_int(data, read, l_d + 1) + 1
            read += l_d + 1
            offset = unpack_little_int(data, read, f_d + 1) + 1
            read += f_d + 1
            opcodes.append((2, offset, length))
            count += length
        # 0110XXDD: run XX for N+35 times, N (0~2^32),
        #           D (0~3) indicates to read D+1 bytes of N, N is packed in little-endian
        elif byte >= 96:
            item = (byte % 16) // 4
            d = byte % 4 + 1
            length = unpack_little_int(data, read, d) + 35
            opcodes.append((1, item, length))
            count += length
            read += d
        # 010LLLLL: Copy from offset=F+1 length=L+1
        #           L (0~31),
        #           this indicates to read next byte as F (0~255)
        elif byte >= 64:
            length = (byte % 32) + 1
            try:
                offset = data[read] + 1
            except IndexError:
                raise ValueError(f"[decode_bit2] Data truncated, expected {total} numbers, got {count}")
            read += 1
            opcodes.append((2, offset, length))
            count += length
        # 001NNNNN: pack N+3 items, N (0~31)
        elif byte >= 32:
            n = byte - 29  # 3-34 items
            packed_count = (n + 3) // 4
            # every packed byte carries 4 items, a stream that ends
            # before them is truncated, check once instead of per byte
            if read + packed_count > len(data):
                raise ValueError(f"[decode_bit2] Data truncated, expected {total} numbers, got {count}")
            remain_n = n
            items = []
            for _ in range(packed_count):
                packed = data[read]
                read += 1
                # each following bytes are AABBCCDD
                if remain_n >= 4:
                    item1 = packed // 64
                    item2 = (packed // 16) % 4
                    item3 = (packed // 4) % 4
                    item4 = packed % 4
                    items.extend([item1, item2, item3, item4])
                    remain_n -= 4
                # trailing 00 to fill up to a full byte, e.g. AABB0000
                elif remain_n == 3:
                    item1 = packed // 64
                    item2 = (packed // 16) % 4
                    item3 = (packed // 4) % 4
                    items.extend([item1, item2, item3])
                    remain_n = 0
                elif remain_n == 2:
                    item1 = packed // 64
                    item2 = (packed // 16) % 4
                    items.extend([item1, item2])
                    remain_n = 0
                elif remain_n == 1:
                    item1 = packed // 64
                    items.append(item1)
                    remain_n = 0
            opcodes.append((0, items))
            count += n
        # 0001XXYY: 2 item
        elif byte >= 16:
            first = (byte % 16) // 4
            second = byte % 4
            opcodes.append((0, [first, second]))
            count += 2
        elif byte >= 4:
            # 000001XX: 1 item, item is 4/5/6/7
            #           This is available when ext8 is enabled
            if ext8 and byte < 8:
                opcodes.append((0, [byte]))
                count += 1
            # invalid: byte>=000000XX
            else:
                raise ValueError(f"[decode_bit2] Invalid opcode: {byte}")
        # 000000XX: 1 item
        elif byte >= 0:
            opcodes.append((0, [byte]))
            count += 1

        # check total
        if count >= total:
            break

    return opcodes, read


def decode_bit2(data, ext8=False):
    """
    Decode bit2 format data to list[int].
    The number of values is read from the vint count prefix, the caller
    does not need to pass it in.

    Args:
        data (memoryview | bytes): Encoded data
        ext8 (bool): True to enable ext8 support to allow 4/5/6/7 as literal values

    Returns:
        tuple[list[int], int]: (list of values, bytes consumed)

    Raises:
        ValueError: If data is truncated or contains invalid opcodes
    """
    if isinstance(data, bytes):
        data = memoryview(data)
    if not data:
        raise ValueError('[decode_bit2] Data truncated: missing vint count prefix')
    total, read = decode_vint(data)
    opcodes, read_stream = decode_bit2_stream_iter(data[read:], total, ext8=ext8)
    read += read_stream
    values = decode_bit2_opcode(opcodes)
    # decode_bit2_stream_iter stops at count >= total, so a run opcode can
    # cross the total boundary and yield more values than declared. This
    # only happens when the stream does not match the count prefix, usually
    # because the input was truncated, raise instead of truncating silently.
    if len(values) != total:
        raise ValueError(
            f'[decode_bit2] Value count mismatch: decoded {len(values)} values, prefix declares {total}')
    return values, read
