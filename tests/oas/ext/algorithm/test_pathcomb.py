"""
Tests for ``oas.ext.algorithm.pathcomb.iter_path_comb``.

The function encodes an ordered path list into
``(prefix_reuse, remaining_path, suffix_reuse, suffix_lookback)`` tuples,
replayed by the decoder as ``prev[:prefix_reuse] + path + lookback[-suffix_reuse:]``.
"""
import pytest

from oas.ext.algorithm.pathcomb import iter_path_comb
from oas.ext.algorithm.pathlen_coding import MAX_PREFIX_REUSE


class TestIterPathCombBasic:
    """Basic prefix/suffix combination encoding."""

    def test_empty(self):
        assert list(iter_path_comb([])) == []

    def test_single_path(self):
        assert list(iter_path_comb(['a.py'])) == [(0, 'a.py', 0, 0)]

    def test_common_suffix_reuse(self):
        """Second path reuses '.png' (4 chars) from the first, lookback 1."""
        assert list(iter_path_comb(['a/1.png', 'b/2.png'])) == [
            (0, 'a/1.png', 0, 0),
            (0, 'b/2', 4, 1),
        ]

    def test_same_basename_different_dirs(self):
        """'/foo.png' (8 chars) is reused from lookback 1."""
        assert list(iter_path_comb(['x/foo.png', 'y/foo.png', 'z/foo.png'])) == [
            (0, 'x/foo.png', 0, 0),
            (0, 'y', 8, 1),
            (0, 'z', 8, 1),
        ]

    def test_dotless_paths(self):
        """Dot-less files still reuse '/README' via the full-path query."""
        assert list(iter_path_comb(['README', 'a/README', 'b/README'])) == [
            (0, 'README', 0, 0),
            (0, 'a/', 6, 1),
            (0, 'b', 7, 1),
        ]


class TestIterPathCombMultiDot:
    """Multi-dot basenames: the LCP stops right before the final dot, the
    stripped path is 'png' (no dot), the full-path query still matches."""

    def test_firefly_pair(self):
        assert list(iter_path_comb([
            'assets/character/Firefly.2.png',
            'assets/character/Firefly.png',
        ])) == [
            (0, 'assets/character/Firefly.2.png', 0, 0),
            (25, '', 3, 1),
        ]

    def test_assignment_pair(self):
        assert list(iter_path_comb([
            'assets/cn/assignment/dispatch/ASSIGNMENT_START.SEARCH.png',
            'assets/cn/assignment/dispatch/ASSIGNMENT_START.png',
        ])) == [
            (0, 'assets/cn/assignment/dispatch/ASSIGNMENT_START.SEARCH.png', 0, 0),
            (47, '', 3, 1),
        ]


class TestIterPathCombSameStemDifferentExt:
    """Same stem, different extension: no cross-suffix match by design; with
    earlier same-suffix files the suffix is reused across the entry."""

    def test_bmp_then_png_no_prior_png(self):
        """LCP stops right before the dot ('f/foo.'), the remaining path is
        'png'; no '.png' bucket exists yet, so nothing is reused."""
        assert list(iter_path_comb(['f/foo.bmp', 'f/foo.png'])) == [
            (0, 'f/foo.bmp', 0, 0),
            (6, 'png', 0, 0),
        ]

    def test_bmp_then_png_with_prior_png(self):
        """'f/foo.png' matches the nearest '.png' at lookback 2, spanning the
        '.bmp' entry."""
        assert list(iter_path_comb(['a/1.png', 'b/2.png', 'f/foo.bmp', 'f/foo.png'])) == [
            (0, 'a/1.png', 0, 0),
            (0, 'b/2', 4, 1),
            (0, 'f/foo.bmp', 0, 0),
            (6, '', 3, 2),
        ]


class TestIterPathCombEdgeCases:
    """MAX_PREFIX_REUSE truncation and zero-length suffix caps."""

    def test_max_prefix_reuse_truncation(self):
        """Prefix reuse longer than MAX_PREFIX_REUSE is truncated, the rest
        stays in the remaining path."""
        long_stem = 'x' * MAX_PREFIX_REUSE
        result = list(iter_path_comb([f'a/{long_stem}.py', f'a/{long_stem}.txt']))
        assert result[1][0] == MAX_PREFIX_REUSE
        assert result[1][1] == 'xx.txt'
        assert result[1][2:] == (0, 0)

    def test_max_prefix_reuse_parameter(self):
        """A custom max_prefix_reuse truncates the reused prefix."""
        result = list(iter_path_comb(
            ['a/abcdefghijklmnopqrstuvwxyz.py', 'a/abcdefghijklmnopqrstuvwxyz.txt'],
            max_prefix_reuse=10))
        assert result[1][0] == 10
        assert result[1][1] == 'ijklmnopqrstuvwxyz.txt'

    def test_duplicate_path(self):
        """Same path twice: the full-path LCS exceeds the stripped path, so
        the suffix is capped to 0 and the lookback is cleared (a kept
        lookback with zero reuse would make the decoder return the whole
        referenced path via ``[-0:]``)."""
        assert list(iter_path_comb(['backend/config.py', 'backend/config.py'])) == [
            (0, 'backend/config.py', 0, 0),
            (17, '', 0, 0),
        ]

    def test_min_suffix_reuse_parameter(self):
        """A custom min_suffix_reuse filters shorter suffixes: '.png' is only
        4 chars, so min_suffix_reuse=5 disables the reuse."""
        result = list(iter_path_comb(['a/1.png', 'b/2.png'], min_suffix_reuse=5))
        assert result[1][2] == 0


class TestIterPathCombPrefixSuffixCrossing:
    """Crossing: prefix and suffix reuse would overlap on the path, the
    full prefix is kept and the suffix is shrunk to fill the rest."""

    def test_crossing_capped(self):
        # C shares its first 20 chars with A ('PPPPPPPPPPPPPPP' + 'QQQQQ')
        # and its last 20 chars with B ('QQQQQ' + 'SSSSSSSSSSSSSSS'),
        # but C is only 35 chars: 20 + 20 would overlap by 5 chars
        a = 'PPPPPPPPPPPPPPPQQQQQ.py'              # 15xP + 5xQ + .py
        b = 'zz/QQQQQSSSSSSSSSSSSSSS'              # zz/ + 5xQ + 15xS
        c = 'PPPPPPPPPPPPPPPQQQQQSSSSSSSSSSSSSSS'  # 15xP + 5xQ + 15xS, len 35
        result = list(iter_path_comb([b, a, c]))
        # prefix=20 from a (prev) kept in full, suffix LCS=20 from b
        # capped to 15 so that prefix + suffix == 35 == len(c)
        assert result[2] == (20, '', 15, 2)

    def test_crossing_keeps_longer_prefix(self):
        # C shares its first 30 chars with A and its last 20 chars with B,
        # but C is only 35 chars: the longer prefix=30 is kept in full,
        # the suffix=20 is shrunk to the remaining 5 chars
        a = 'AAAAAAAAAAAAAAAAAAAAAAAAABBBBB.py'  # 25xA + 5xB + .py
        b = 'zz/AAAAAAAAAABBBBBCCCCC'            # zz/ + 10xA + 5xB + 5xC
        c = 'AAAAAAAAAAAAAAAAAAAAAAAAABBBBBCCCCC'  # 25xA + 5xB + 5xC, len 35
        result = list(iter_path_comb([b, a, c]))
        assert result[2] == (30, '', 5, 2)

    def test_crossing_exact_fit(self):
        """Suffix LCS shorter than the remaining path needs no cap."""
        a = 'PPPPPPPPPPPPPPPQQQQQ.py'                      # 15xP + 5xQ + .py
        b = 'zz/QQQQQSSSSSSSSSSSSSSS'                      # zz/ + 5xQ + 15xS
        c = 'PPPPPPPPPPPPPPPQQQQQXXXXXQQQQQSSSSSSSSSSSSSSS'  # len 45
        result = list(iter_path_comb([b, a, c]))
        # prefix=20, remaining=25, suffix LCS=20 fits without capping
        assert result[2] == (20, 'XXXXX', 20, 2)


class TestIterPathCombRoundtrip:
    """Rebuild full paths from the yields using the decoder's replay
    semantics: ``prev[:prefix_reuse] + path + lookback[-suffix_reuse:]``."""

    @pytest.mark.parametrize("paths", [
        ['assets/character/Firefly.2.png', 'assets/character/Firefly.png'],
        ['assets/cn/assignment/dispatch/ASSIGNMENT_START.SEARCH.png',
         'assets/cn/assignment/dispatch/ASSIGNMENT_START.png'],
        ['a/1.png', 'b/2.png', 'f/foo.bmp', 'f/foo.png'],
        ['README', 'a/README', 'b/README'],
        ['x/foo.png', 'y/foo.png', 'z/foo.png'],
        ['backend/config.py', 'backend/config.py'],
        ['a.py'],
        [],
        # crossing: prefix=20 from prev, suffix=20 from lookback 2, capped to 15
        ['zz/QQQQQSSSSSSSSSSSSSSS', 'PPPPPPPPPPPPPPPQQQQQ.py',
         'PPPPPPPPPPPPPPPQQQQQSSSSSSSSSSSSSSS'],
    ])
    def test_rebuild(self, paths):
        rebuilt = []
        prev = ''
        for prefix_reuse, remaining, suffix_reuse, suffix_lookback in iter_path_comb(paths):
            if suffix_lookback:
                suffix = rebuilt[-suffix_lookback][-suffix_reuse:]
            else:
                suffix = ''
            path = prev[:prefix_reuse] + remaining + suffix
            rebuilt.append(path)
            prev = path
        assert rebuilt == paths
