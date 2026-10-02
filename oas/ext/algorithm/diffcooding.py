def encode_diff_gen(numbers):
    """
    Internal generator: yield deltas.

    Args:
        numbers (list[int]): List of integers to encode.

    Yields:
        int: Delta from the previous value.
    """
    prev = 0
    for curr in numbers:
        yield curr - prev
        prev = curr


def decode_diff_gen(encoded):
    """
    Internal generator: yield reconstructed values.

    Args:
        encoded (list[int]): Differentially encoded integers.

    Yields:
        int: Reconstructed value.
    """
    prev = 0
    for delta in encoded:
        curr = prev + delta
        yield curr
        prev = curr


def encode_diff(numbers):
    """
    Encode a list of integers using differential coding.

    Each element is stored as the delta from the previous value, with the
    first element using 0 as the implicit previous value.
    The output has the same length as the input.

    Args:
        numbers (list[int]): List of integers to encode.

    Returns:
        list[int]: Differentially encoded integers.
    """
    return list(encode_diff_gen(numbers))


def decode_diff(encoded):
    """
    Decode a differentially encoded list of integers back to the original
    sequence.

    Args:
        encoded (list[int]): Differentially encoded integers produced by
            :func:`encode_diff`.

    Returns:
        list[int]: Decoded original integers.
    """
    return list(decode_diff_gen(encoded))
