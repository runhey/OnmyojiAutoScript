from collections import deque

from oas.ext.algorithm.const import MAX_INT64


def decode_vint(data):
    """
    Decode Bijective Variable-length Integer
    Note that this is not the vint in protobuf, this is the vint in git offset

    Note that python has special optimization for small int (-5~256) but bitwise operation is in int64
    You should use + - * / % instead of & | >>

    Args:
        data (bytearray | bytes | memoryview): Data to decode

    Returns:
        tuple[int, int]: (decoded_integer, bytes_read)

    Raises:
        ValueError: If the decoded value exceeds INT64
        ValueError: If the data is truncated, empty or a high byte at the
            end of the stream without a following terminating byte
    """
    if not data:
        raise ValueError("[decode_vint] Data truncated: empty input")
    num = 0
    read = 1
    for byte in data:
        # add in the next 7 bits of data
        if byte >= 128:
            # see parse_ofs_delta()
            # byte & 0x7f + 1
            num += byte - 127
            num *= 128
            read += 1
            # With at most 7 high bytes the value stays below INT64 (max ~7.3e16)
            # From the 8th high byte on it may exceed INT64, compare only then
            # to keep the common path free of big integer comparisons
            if read > 8 and num > MAX_INT64:
                raise ValueError(f"[decode_vint] Decoded value exceeds INT64: {num}")
        else:
            num += byte
            if read > 8 and num > MAX_INT64:
                raise ValueError(f"[decode_vint] Decoded value exceeds INT64: {num}")
            break
    else:
        # no terminating byte (MSB clear) found, the stream ended inside the vint
        raise ValueError("[decode_vint] Data truncated: stream ended inside the vint")

    return num, read


def encode_vint(num):
    """
    Encode Bijective Variable-length Integer
    Note that this is not the vint in protobuf, this is the vint in git offset

    Note that python has special optimization for small int (-5~256) but bitwise operation is in int64
    You should use + - * / % instead of & | >>

    Bijective base-128 representation:
        - Least significant digit in [0, 127], stored directly (MSB clear)
        - All other digits in [1, 128], stored as digit + 127 (MSB set)
        - When a non-least-significant digit is 0, borrow: set digit to 128 and decrement the carry

    Args:
        num (int): Non-negative integer to encode

    Returns:
        bytes: Encoded bytes

    Raises:
        ValueError: If num is negative or exceeds INT64
    """
    if num < 0:
        raise ValueError(f"[encode_vint] Value is negative: {num}")
    if num > MAX_INT64:
        raise ValueError(f"[encode_vint] Value is too large: {num}")
    result = deque()
    result.append(num % 128)
    while num > 127:
        # num = (num >> 7) - 1
        num //= 128
        num -= 1
        # insert at head, set MSB=1
        # (num & 0x7f) | 0x80
        result.appendleft(128 + num % 128)

    return bytes(result)


def decode_vint_list(data, total):
    """
    Decode a sequence of vint-encoded integers from bytes.

    Args:
        data (bytearray | bytes | memoryview): Encoded data containing total vint-encoded integers
        total (int): Number of integers to decode

    Returns:
        tuple[list[int], int]: (list[decoded_integer], total_bytes_read)

    Raises:
        ValueError: If total is not positive
        ValueError: If any decoded value exceeds INT64
        ValueError: If the data is truncated, empty or a high byte at the
            end of the stream without a following terminating byte
    """
    if total <= 0:
        raise ValueError(f"[decode_vint_list] Total must be positive: {total}")
    if not data:
        raise ValueError("[decode_vint_list] Data truncated: empty input")
    num_list = []
    num = 0
    read = 0
    total_read = 0
    count = 0
    for byte in data:
        # add in the next 7 bits of data
        if byte >= 128:
            # see parse_ofs_delta()
            # byte & 0x7f + 1
            num += byte - 127
            num *= 128
            read += 1
            # With at most 7 high bytes the value stays below INT64 (max ~7.3e16)
            # From the 8th high byte on it may exceed INT64, compare only then
            # to keep the common path free of big integer comparisons
            if read > 8 and num > MAX_INT64:
                raise ValueError(f"[decode_vint_list] Decoded value exceeds INT64: {num}")
        else:
            num += byte
            read += 1
            if read > 8 and num > MAX_INT64:
                raise ValueError(f"[decode_vint_list] Decoded value exceeds INT64: {num}")
            # end of num
            count += 1
            num_list.append(num)
            total_read += read
            num = 0
            read = 0
        if count >= total:
            break

    # the stream ended inside a vint: the last byte had its MSB set and
    # promised more bytes that are not there
    if read > 0:
        raise ValueError("[decode_vint_list] Data truncated: stream ended inside a vint")

    return num_list, total_read


def encode_vint_list(list_num):
    """
    Encode a list of integers as concatenated vint bytes.

    Args:
        list_num (list[int]): List of non-negative integers to encode

    Returns:
        bytes: Encoded bytes, concatenation of each vint-encoded integer

    Raises:
        ValueError: If any integer is negative or exceeds INT64
    """
    result_list = deque()
    for num in list_num:
        if num < 0:
            raise ValueError(f"[encode_vint_list] Value is negative: {num}")
        if num > MAX_INT64:
            raise ValueError(f"[encode_vint_list] Value is too large: {num}")
        result = deque()
        result.append(num % 128)
        while num > 127:
            # num = (num >> 7) - 1
            num //= 128
            num -= 1
            # insert at head, set MSB=1
            # (num & 0x7f) | 0x80
            result.appendleft(128 + num % 128)

        result_list.extend(result)

    return bytes(result_list)
