"""
The encoder of the filepath section of a pack index: the C encoder when the
accelerator of oas_speedup is installed, the pure Python pipeline
otherwise.

Importing this module is what looks for the accelerator (see
oas.speedup): it scans the site-packages, loads the installed
oas_speedup, builds its library on first use and checks its interface
version and its frozen parameters. Anything that fails on the way, a machine
without a compiler included, falls back to iter_path_comb() of
pathcomb_encode_python.py and the two combined encoders of the same module,
so a caller always gets an encoder. The reason of a fallback is in
oas.speedup.ERRORS['pathcomb'].

Unlike the bit2 encoder, the two implementations emit the very same bytes:
the accelerator replaces the search, not the format, and the tests compare
it against the Python reference on every branch of the search.
"""
from oas.ext.algorithm.pathcomb.pathcomb_encode_python import (
    MAX_PREFIX_REUSE, MAX_SUFFIX_LOOKBACK, MAX_SUFFIX_REUSE, MIN_SUFFIX_REUSE,
    encode_prefix_comb as encode_prefix_comb_python, encode_suffix_comb as encode_suffix_comb_python, iter_path_comb
)
try:
    from oas.speedup import accelerator
except ImportError:
    def accelerator(_name):
        return None

# the frozen parameters of the encoder, in the order of the C one: the pack
# format is what decides of the bytes, so an accelerator built for another
# set of them is refused below instead of being called
PARAMS = (MAX_PREFIX_REUSE, MIN_SUFFIX_REUSE, MAX_SUFFIX_REUSE, MAX_SUFFIX_LOOKBACK)

_pathcomb = accelerator('pathcomb')

if _pathcomb is not None and _pathcomb.PARAMS != PARAMS:
    # a library built from other constants would emit other bytes with no
    # error at all, the Python pipeline of this module stays the reference
    _pathcomb = None


if _pathcomb is not None:
    def encode_path_comb(paths):
        """
        Encode the filepath section of a pack index, with the C encoder.

        Args:
            paths (Iterable[str]): Full paths in encoded order

        Returns:
            tuple[list[int], list[int], bytes]: Combined prefix values,
                combined suffix values and the remaining paths concatenated
        """
        return _pathcomb.encode_path_comb(paths)

    def encode_prefix_comb(prefix_reuse, path_length):
        """
        Encode the prefix reuse and the remaining path lengths into the
        combined ints, with the C encoder.

        Args:
            prefix_reuse (Iterable[int]): Prefix reuse of every path
            path_length (Iterable[int]): Remaining path byte lengths

        Returns:
            list[int]: Combined values, same length as the input
        """
        return _pathcomb.encode_prefix_comb(prefix_reuse, path_length)

    def encode_suffix_comb(suffix_reuse, suffix_lookback):
        """
        Encode the suffix reuse and the lookback distances into the combined
        ints, with the C encoder.

        Args:
            suffix_reuse (Iterable[int]): Suffix reuse of every path
            suffix_lookback (Iterable[int]): Lookback distances

        Returns:
            list[int]: Combined values, same length as the input
        """
        return _pathcomb.encode_suffix_comb(suffix_reuse, suffix_lookback)
else:
    encode_prefix_comb = encode_prefix_comb_python
    encode_suffix_comb = encode_suffix_comb_python

    def encode_path_comb(paths):
        """
        Encode the filepath section of a pack index, with the pure Python
        pipeline: the search of iter_path_comb() and the two combined
        encoders, the reference of the C encoder.

        Args:
            paths (Iterable[str]): Full paths in encoded order

        Returns:
            tuple[list[int], list[int], bytes]: Combined prefix values,
                combined suffix values and the remaining paths concatenated
        """
        list_path = []
        list_prefix_reuse = []
        list_suffix_reuse = []
        list_suffix_lookback = []
        for prefix_reuse, path, suffix_reuse, suffix_lookback in iter_path_comb(paths):
            list_prefix_reuse.append(prefix_reuse)
            list_suffix_reuse.append(suffix_reuse)
            list_suffix_lookback.append(suffix_lookback)
            # remaining path, empty when fully reused by prefix + suffix
            list_path.append(path.encode())

        # remaining path byte lengths, 0 for fully reused paths
        return (
            encode_prefix_comb(list_prefix_reuse, [len(path) for path in list_path]),
            encode_suffix_comb(list_suffix_reuse, list_suffix_lookback),
            b''.join(list_path),
        )
