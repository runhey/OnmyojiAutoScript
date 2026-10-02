def encode_zigzag_iter(data):
    """
    Encode data to zigzag format
    0 -> 0, -1 -> 1, 1 -> 2, -2 -> 3, 2 -> 4, -3 -> 5, ...

    Args:
        data (list[int] | deque[int]): Data to encode

    Yields:
        int: Encoded data
    """
    for i in data:
        if i >= 0:
            yield i * 2
        else:
            yield -i * 2 - 1


def encode_zigzag(data):
    """
    Encode data to zigzag format
    0 -> 0, -1 -> 1, 1 -> 2, -2 -> 3, 2 -> 4, -3 -> 5, ...

    Args:
        data (list[int] | deque[int]): Data to encode

    Returns:
        list[int]: Encoded data
    """
    return list(encode_zigzag_iter(data))


def decode_zigzag_iter(data):
    """
    Decode zigzag format data to list[int]
    0 -> 0, 1 -> -1, 2 -> 1, 3 -> -2, 4 -> 2, 5 -> -3, ...

    Args:
        data (list[int] | deque[int]): Encoded data

    Yields:
        int: Decoded data
    """
    for i in data:
        if i % 2 == 1:
            yield (-i - 1) // 2
        else:
            yield i // 2


def decode_zigzag(data):
    """
    Decode zigzag format data to list[int]
    0 -> 0, 1 -> -1, 2 -> 1, 3 -> -2, 4 -> 2, 5 -> -3, ...

    Args:
        data (list[int] | deque[int]): Encoded data

    Returns:
        list[int]: Decoded data
    """
    return list(decode_zigzag_iter(data))
