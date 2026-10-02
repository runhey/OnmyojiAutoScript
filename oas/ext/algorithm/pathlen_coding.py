"""
Combined encoding for path-based data: prefix (diff+zigzag) and suffix (nibble).
"""
from oas.ext.algorithm.diffcooding import decode_diff, encode_diff
from oas.ext.algorithm.zigzag import decode_zigzag, encode_zigzag

# MAX_PREFIX_REUSE is bounded by the combined-int encoding, not by the field
# width itself. prefix_reuse is diff-encoded then zigzagged, so a single value
# of N can produce a zigzag diff of up to 2N (diff = +N -> zz = 2N).
# The combined int must stay < 2**32 for vlenint:
#   2**24 + zz * 65536 + pl <= 2**32 - 1, for any pl <= 65535
#   -> zz <= 65279, so N <= 65279 // 2 = 32639
# Limiting the single value (instead of the diff) keeps the constraint easy
# to satisfy for callers: any adjacent values in [0, MAX_PREFIX_REUSE] are
# always encodable, no matter how they jump.
MAX_PREFIX_REUSE = 32639
MAX_PATH_LEN = 65535
MAX_SUFFIX_REUSE = 65535
MAX_SUFFIX_LOOKBACK = 255

_1B1B_BIAS = 256
_2B2B_BIAS = 16777216  # 2 ** 24


def prefix_comb_value_check(list_prefix_reuse, list_path_length):
    """
    Check if the input values are valid for prefix_comb encoding.

    All prefix_reuse values must be in [0, MAX_PREFIX_REUSE] and all
    path_length values in [0, MAX_PATH_LEN]. Since every value is bounded
    by MAX_PREFIX_REUSE, adjacent diffs are bounded too, so the zigzag diff
    never exceeds 2 * MAX_PREFIX_REUSE <= 65279 -- the capacity of the
    2B+2B combined format. Values passing this check are always encodable.

    Args:
        list_prefix_reuse (list[int] | deque[int]): raw prefix lengths.
        list_path_length (list[int] | deque[int]): remaining path lengths.

    Raises:
        ValueError: If any value is negative, exceeds limit, or lengths differ.
    """
    if len(list_prefix_reuse) != len(list_path_length):
        raise ValueError(
            f'list_prefix_reuse and list_path_length must have same length, '
            f'got {len(list_prefix_reuse)} vs {len(list_path_length)}'
        )
    if not list_prefix_reuse:
        return
    min_pr = min(list_prefix_reuse)
    max_pr = max(list_prefix_reuse)
    if min_pr < 0:
        raise ValueError(f'prefix_reuse must be >= 0, got {min_pr}')
    if max_pr > MAX_PREFIX_REUSE:
        raise ValueError(f'prefix_reuse must be <= {MAX_PREFIX_REUSE}, got {max_pr}')
    min_pl = min(list_path_length)
    max_pl = max(list_path_length)
    if min_pl < 0:
        raise ValueError(f'path_len must be >= 0, got {min_pl}')
    if max_pl > MAX_PATH_LEN:
        raise ValueError(f'path_len must be <= {MAX_PATH_LEN}, got {max_pl}')


def suffix_comb_value_check(list_suffix_reuse, list_suffix_lookback):
    """
    Check if the input values are valid for suffix_comb encoding.

    Args:
        list_suffix_reuse (list[int] | deque[int]): must be <= 65535.
        list_suffix_lookback (list[int] | deque[int]): must be <= 255.

    Raises:
        ValueError: If any value is negative, exceeds limit, or lengths differ.
    """
    if len(list_suffix_reuse) != len(list_suffix_lookback):
        raise ValueError(
            f'list_suffix_reuse and list_suffix_lookback must have same length, '
            f'got {len(list_suffix_reuse)} vs {len(list_suffix_lookback)}'
        )
    if not list_suffix_reuse:
        return
    min_sr = min(list_suffix_reuse)
    max_sr = max(list_suffix_reuse)
    if min_sr < 0:
        raise ValueError(f'suffix_reuse must be >= 0, got {min_sr}')
    if max_sr > MAX_SUFFIX_REUSE:
        raise ValueError(f'suffix_reuse must be <= {MAX_SUFFIX_REUSE}, got {max_sr}')
    min_lb = min(list_suffix_lookback)
    max_lb = max(list_suffix_lookback)
    if min_lb < 0:
        raise ValueError(f'suffix_lookback must be >= 0, got {min_lb}')
    if max_lb > MAX_SUFFIX_LOOKBACK:
        raise ValueError(f'suffix_lookback must be <= {MAX_SUFFIX_LOOKBACK}, got {max_lb}')


def _encode_prefix_comb_iter(list_prefix_reuse, list_path_length):
    """
    Encode prefix_reuse (after diff+zigzag) and path_len into combined ints.

    Encoding scheme (1 int per entry):
        zz < 32  and pl < 8:   zz * 8 + pl                       (< 256)
            ~78.7% in ALAS, ~63.4% in SRC
        pl < 256 and zz < 65535:
            zz * 256 + pl + _1B1B_BIAS                            (< 2^24)
            1B+1B (zz < 256):    ~21.3% in ALAS, ~36.6% in SRC
            2B+1B (zz >= 256):   ~0.0% in both repos
        else:
            _2B2B_BIAS + zz * 65536 + pl                          (>= 2^24)
            ~0.0% in ALAS, ~0.0% in SRC (theoretical, for pl >= 256)

    zz = encode_zigzag(encode_diff(list_prefix_reuse))

    With prefix_reuse <= MAX_PREFIX_REUSE, the zigzag diff is bounded:
        zz <= 2 * MAX_PREFIX_REUSE = 65278 < 65535
    so the 2B+2B format only triggers on pl >= 256 (the zz >= 65535 branch
    is unreachable), and every output is < 2**32, compatible with vlenint.

    Args:
        list_prefix_reuse (list[int] | deque[int]): raw prefix lengths.
            Must be <= MAX_PREFIX_REUSE.
        list_path_length (list[int] | deque[int]): remaining path lengths.
            Must be <= MAX_PATH_LEN.

    Yields:
        int: Combined encoded integer per input pair.
    """
    zz_list = encode_zigzag(encode_diff(list_prefix_reuse))
    for zz, pl in zip(zz_list, list_path_length):
        if zz < 32 and pl < 8:
            yield zz * 8 + pl
        elif pl < 256:
            if zz < 65535:
                yield zz * 256 + pl + _1B1B_BIAS
            else:
                yield _2B2B_BIAS + zz * 65536 + pl
        else:
            yield _2B2B_BIAS + zz * 65536 + pl


def encode_prefix_comb(list_prefix_reuse, list_path_length):
    """
    Encode prefix_reuse (after diff+zigzag) and path_len jointly.

    Each input pair produces exactly 1 output integer, in one of 3 formats:
    5b+3b, biased 1B+1B or biased 2B+2B. Apply diff+zigzag to prefix_reuse
    internally, then combine. Every output is < 2**32, so the result can be
    fed into encode_vlenint directly.

    Args:
        list_prefix_reuse (list[int] | deque[int]): raw prefix lengths.
            Must be <= MAX_PREFIX_REUSE.
        list_path_length (list[int] | deque[int]): remaining path lengths.
            Must be <= MAX_PATH_LEN.

    Returns:
        list[int]: Encoded list, same length as input.
    """
    prefix_comb_value_check(list_prefix_reuse, list_path_length)
    return list(_encode_prefix_comb_iter(list_prefix_reuse, list_path_length))


def decode_prefix_comb(encoded):
    """
    Decode prefix_comb encoded data.

    Decoding ranges:
        v < 256:              5b+3b: zz = v // 8,  pl = v % 8
        256 <= v < 2^24:      1B/2B zz + 1B pl:   raw = v - _1B1B_BIAS,
                                                    zz = raw // 256, pl = raw % 256
        v >= 2^24:            2B zz + 2B pl:       raw = v - _2B2B_BIAS,
                                                    zz = raw // 65536, pl = raw % 65536

    Args:
        encoded (list[int]): Encoded integers from encode_prefix_comb.

    Returns:
        tuple[list[int], list[int]]: (prefix_reuse, path_len).
    """
    zz_list = []
    pl_list = []
    for v in encoded:
        if v < 256:
            zz = v // 8
            pl = v % 8
        elif v < _2B2B_BIAS:
            raw = v - _1B1B_BIAS
            zz = raw // 256
            pl = raw % 256
        else:
            raw = v - _2B2B_BIAS
            zz = raw // 65536
            pl = raw % 65536
        zz_list.append(zz)
        pl_list.append(pl)

    diff_list = decode_zigzag(zz_list)
    prefix_reuse = decode_diff(diff_list)
    return prefix_reuse, pl_list


def _encode_suffix_comb_iter(list_suffix_reuse, list_suffix_lookback):
    """
    Encode suffix_reuse and suffix_lookback into combined ints.

    Encoding scheme (1 int per entry):
        both 0:                   0                                   (= 0)
            ~4.7% in ALAS, ~11.3% in SRC
        reuse < 16 and lb < 16:   reuse * 16 + lb                    (< 256)
            ~51.9% in ALAS, ~47.3% in SRC
        else:                     reuse * 256 + lb + _1B1B_BIAS      (>= 256)
            ~43.3% in ALAS, ~41.4% in SRC

    Args:
        list_suffix_reuse (list[int] | deque[int]): must <= 65535.
        list_suffix_lookback (list[int] | deque[int]): must <= 255.

    Yields:
        int: Combined encoded integer per input pair.
    """
    for reuse, lb in zip(list_suffix_reuse, list_suffix_lookback):
        if reuse == 0 and lb == 0:
            yield 0
        elif reuse < 16 and lb < 16:
            yield reuse * 16 + lb
        else:
            # biased by +256 to avoid range overlap with nibble format
            yield reuse * 256 + lb + _1B1B_BIAS


def encode_suffix_comb(list_suffix_reuse, list_suffix_lookback):
    """
    Nibble encode suffix_reuse and suffix_lookback to 1 int if possible.

    Args:
        list_suffix_reuse (list[int] | deque[int]): must be <= 65535.
        list_suffix_lookback (list[int] | deque[int]): must be <= 255.

    Returns:
        list[int]: Encoded list, same length as input.
    """
    suffix_comb_value_check(list_suffix_reuse, list_suffix_lookback)
    return list(_encode_suffix_comb_iter(list_suffix_reuse, list_suffix_lookback))


def decode_suffix_comb(encoded):
    """
    Decode suffix_comb encoded data.

    Decoding ranges:
        v == 0:                  (0, 0) = no match
        v < 256:                 reuse = v // 16, lb = v % 16
        v >= 256:                raw = v - _1B1B_BIAS,
                                 reuse = raw // 256, lb = raw % 256

    Args:
        encoded (list[int]): Encoded integers from encode_suffix_comb.

    Returns:
        tuple[list[int], list[int]]: (suffix_reuse, suffix_lookback).
    """
    reuse_list = []
    lb_list = []
    for v in encoded:
        if v == 0:
            reuse = 0
            lb = 0
        elif v < 256:
            reuse = v // 16
            lb = v % 16
        else:
            raw = v - _1B1B_BIAS
            reuse = raw // 256
            lb = raw % 256
        reuse_list.append(reuse)
        lb_list.append(lb)

    return reuse_list, lb_list
