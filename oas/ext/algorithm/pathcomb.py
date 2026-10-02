"""
Path combination encoding: prefix reuse + remaining path + suffix reuse.

``iter_path_comb()`` is the shared encoder for ordered path lists (e.g. the
index section of a pack).  For each input path it yields:

- ``prefix_reuse``: length of the longest common prefix with the previous path
- ``path``: the remaining path after stripping the reused prefix and suffix
- ``suffix_reuse``: length of the suffix reused from a lookback path
- ``suffix_lookback``: 1-based distance to the reused suffix's path

The decoder (``decode_base._decode_paths``) replays these values as
``prev[:prefix_reuse] + path + lookback_path[-suffix_reuse:]``.
"""
from typing import Iterable, Iterator, Tuple

from oas.ext.algorithm.lcp import get_lcp
from oas.ext.algorithm.pathlcs import PathLookbackLCS
from oas.ext.algorithm.pathlen_coding import MAX_PREFIX_REUSE, MAX_SUFFIX_LOOKBACK, MAX_SUFFIX_REUSE


def iter_path_comb(
        paths: "Iterable[str]",
        max_prefix_reuse=MAX_PREFIX_REUSE,
        min_suffix_reuse=3,
        max_suffix_reuse=MAX_SUFFIX_REUSE,
        max_suffix_lookback=MAX_SUFFIX_LOOKBACK,
) -> "Iterator[Tuple[int, str, int, int]]":
    """
    Encode an ordered path list into prefix/suffix combination values.

    Args:
        paths (Iterable[str]): Full paths in encoded order
        max_prefix_reuse (int): Maximum prefix length reused from the
            previous path. Defaults to MAX_PREFIX_REUSE.
        min_suffix_reuse (int): Minimum LCS length for a suffix candidate.
            Defaults to 3.
        max_suffix_reuse (int): Maximum LCS length for a suffix candidate.
            Defaults to MAX_SUFFIX_REUSE.
        max_suffix_lookback (int): Maximum lookback distance for a suffix
            candidate. Defaults to MAX_SUFFIX_LOOKBACK.

    Yields:
        tuple[int, str, int, int]: prefix_reuse, remaining path, suffix_reuse,
            suffix_lookback
    """
    prev = ''
    lcs_lookback = PathLookbackLCS()
    for path in paths:
        # prefix
        prefix_reuse = get_lcp(prev, path)
        # prefix_reuse must <= max_prefix_reuse
        # otherwise the zigzag diff may overflow the combined-int encoding
        if len(prefix_reuse) > max_prefix_reuse:
            prefix_reuse = prefix_reuse[:max_prefix_reuse]
        remaining = path.removeprefix(prefix_reuse)

        # suffix, query with the full path consistent with add_path() below and
        # with the decoder, which takes suffixes from full lookback paths;
        # a prefix-stripped path may lose its extension dot (e.g. "png")
        # and can never match the ('.png', ...) buckets of stored paths
        suffix_lookback, suffix_reuse = lcs_lookback.get_lcs(
            path, min_length=min_suffix_reuse, max_length=max_suffix_reuse, max_lookback=max_suffix_lookback,
        )
        # the LCS of full paths may extend beyond the prefix-stripped path
        # (e.g. ".png" vs stripped "png"); cap it so the suffix always fits
        # the remaining path, keeping prefix and suffix non-overlapping.
        # On a crossing, keep the full prefix (up to max_prefix_reuse) and
        # shrink the suffix to fill the remaining space.
        if suffix_reuse > len(remaining):
            suffix_reuse = len(remaining)
            # a zero-length reuse must not keep a lookback: the decoder
            # takes ``paths[i-lookback][-suffix_reuse:]`` and ``[-0:]``
            # would yield the whole referenced path instead of nothing
            if not suffix_reuse:
                suffix_lookback = 0
        if suffix_reuse:
            remaining = remaining[:-suffix_reuse]
        lcs_lookback.add_path(path)
        prev = path

        yield len(prefix_reuse), remaining, suffix_reuse, suffix_lookback
