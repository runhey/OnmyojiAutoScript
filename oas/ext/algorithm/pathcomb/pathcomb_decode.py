"""
The decoders of the two combined encodings of the filepath section of a
pack index.

The encoder of the section is pathcomb_encode_python.py, its accelerator is
oas_speedup.pathcomb, both of them emit what these two functions read:
one int per entry, the prefix reuse (after a differential + zigzag) combined
with the remaining path byte length, the suffix reuse combined with the
lookback distance of the path it reuses. The pack decoder replays the paths
with them, see _decode_paths() of oas.deploy.pack.decode_base.
"""
from oas.ext.algorithm.diffcooding import decode_diff
from oas.ext.algorithm.zigzag import decode_zigzag

# biases of the combined encoding, one per format range, they belong to the
# format and the encoder imports them from here: the client side decodes
# without ever loading an encoder
_1B1B_BIAS = 256
_2B2B_BIAS = 16777216  # 2 ** 24


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
