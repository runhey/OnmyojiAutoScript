"""
Tests for ``oas.ext.algorithm.pathlcs.PathLookbackLCS``.

V1 uses a three-level fallback strategy based on ``(suffix, last_char, lsecond)``
bucketing:

  1. Match within the exact ``(suffix, last, second)`` bucket (actual LCS).
  2. Fallback: match within the same ``(suffix, last)`` — uses a fixed length of
     ``len(suffix) + len(last)``.
  3. Fallback: match within the same ``suffix`` — picks the suffix with the best
     LCS to the query suffix, then returns the highest-indexed entry from that
     bucket.

.. note::
   V1 does **not** have a Level-4 cross-suffix fallback (that was added in V2).
"""

from __future__ import annotations

import pytest

from oas.ext.algorithm.pathlcs import PathLookbackLCS

# ---------------------------------------------------------------------------
# Tests for get_key()
# ---------------------------------------------------------------------------


class TestGetKey:
    """PathLookbackLCS.get_key() -> (suffix, last_char, lsecond)."""

    @pytest.mark.parametrize("path, suffix, char, lsecond", [
        # Standard paths
        ("foo/bar/baz.py", ".py", "z", "a"),
        ("foo/bar/baz.txt", ".txt", "z", "a"),
        ("/etc/config.yaml", ".yaml", "g", "i"),
        # No extension — stem keeps last and second-to-the-last chars
        ("foo/bar/baz", "", "z", "a"),
        # Multiple dots — last dot wins
        ("foo/bar.baz.tar.gz", ".gz", "r", "a"),
        ("some.dir/file.txt", ".txt", "e", "l"),
        # Dotfiles
        ("foo/.gitignore", ".gitignore", "", ""),
        ("foo/.bashrc", ".bashrc", "", ""),
        (".gitignore", ".gitignore", "", ""),
        # Empty / special
        ("", "", "", ""),
        (".", ".", "", ""),
        # Single-char stem
        ("a.py", ".py", "a", ""),
        ("ab.py", ".py", "b", "a"),
        # Unicode
        ("目录/文件.py", ".py", "件", "文"),
        # Backslash path (Windows-style)
        ("C:\\\\Users\\\\me\\\\file.py", ".py", "e", "l"),
    ])
    def test_get_key(self, path, suffix, char, lsecond):
        assert PathLookbackLCS.get_key(path) == (suffix, char, lsecond)


# ---------------------------------------------------------------------------
# Tests for add_path()
# ---------------------------------------------------------------------------


class TestAddPath:
    """PathLookbackLCS.add_path() stores a path with a monotonically
    increasing index under the correct (suffix, last, lsecond) bucket."""

    def test_add_first_path(self):
        lcs = PathLookbackLCS()
        lcs.add_path("foo.py")
        assert lcs.index == 1
        assert lcs.dict_suffix[".py"]["o"]["o"] == {"foo.py": 0}

    def test_add_multiple_paths(self):
        lcs = PathLookbackLCS()
        lcs.add_path("a.py")
        lcs.add_path("b.py")
        lcs.add_path("c.py")
        assert lcs.index == 3

    def test_add_paths_different_suffix(self):
        lcs = PathLookbackLCS()
        lcs.add_path("a.py")
        lcs.add_path("b.txt")
        assert ".py" in lcs.dict_suffix
        assert ".txt" in lcs.dict_suffix

    def test_add_paths_same_char_different_lsecond(self):
        """Same (suffix, char) but different lsecond go to different buckets."""
        lcs = PathLookbackLCS()
        lcs.add_path("aba.py")          # stem "aba", char='a', lsecond='b'
        lcs.add_path("aca.py")          # stem "aca", char='a', lsecond='c'
        assert "b" in lcs.dict_suffix[".py"]["a"]
        assert "c" in lcs.dict_suffix[".py"]["a"]

    def test_add_paths_same_suffix_different_char(self):
        lcs = PathLookbackLCS()
        lcs.add_path("xa.py")
        lcs.add_path("xb.py")
        assert "a" in lcs.dict_suffix[".py"]
        assert "b" in lcs.dict_suffix[".py"]

    def test_add_duplicate_path(self):
        lcs = PathLookbackLCS()
        lcs.add_path("foo.py")
        lcs.add_path("foo.py")
        assert lcs.dict_suffix[".py"]["o"]["o"]["foo.py"] == 1
        assert lcs.index == 2


# ---------------------------------------------------------------------------
# Level 1: exact (suffix, last, lsecond) bucket
# ---------------------------------------------------------------------------


class TestGetLcsLevel1:
    """Level 1 — match within the exact (suffix, last, lsecond) bucket using
    actual LCS (longest common suffix) between the full paths."""

    def test_empty_lookback(self):
        """No paths added -> (0, 0)."""
        lookback, length = PathLookbackLCS().get_lcs("foo.py")
        assert lookback == 0
        assert length == 0

    def test_empty_query_no_paths(self):
        lookback, length = PathLookbackLCS().get_lcs("")
        assert lookback == 0
        assert length == 0

    def test_exact_match_short_circuit(self):
        """When LCS length equals the query's full length (i.e. the stored path
        has the entire query as a suffix), return immediately."""
        lcs = PathLookbackLCS()
        lcs.add_path("foo/bar.py")       # idx 0
        lcs.add_path("other.py")         # idx 1
        lookback, length = lcs.get_lcs("foo/bar.py")
        # LCS("foo/bar.py", "foo/bar.py") == len("foo/bar.py") -> short circuit
        assert lookback == 2
        assert length == len("foo/bar.py")

    def test_exact_match_fresh_path(self):
        lcs = PathLookbackLCS()
        lcs.add_path("abc_def.py")       # idx 0
        lcs.add_path("xyz_def.py")       # idx 1
        lookback, length = lcs.get_lcs("xyz_def.py")
        assert lookback == 1
        assert length == len("xyz_def.py")

    def test_exact_duplicate_paths(self):
        """Same path added twice — the latest index is used."""
        lcs = PathLookbackLCS()
        lcs.add_path("common.py")        # idx 0
        lcs.add_path("other.py")         # idx 1
        lcs.add_path("common.py")        # idx 2
        lookback, length = lcs.get_lcs("common.py")
        # The dict has {"common.py": 2}, so current_index=3, lookback=1
        assert lookback == 1
        assert length == len("common.py")

    @pytest.mark.parametrize("paths, query, expected_lookback, expected_length", [
        (["aaaaa.py", "bbaaa.py", "cccc.py"], "xxaaa.py", 2, 6),
        (["ab.py", "cb.py"], "xb.py", 1, 4),
    ])
    def test_best_match(self, paths, query, expected_lookback, expected_length):
        """Best LCS among candidates in the same sub-bucket."""
        lcs = PathLookbackLCS()
        for p in paths:
            lcs.add_path(p)
        lookback, length = lcs.get_lcs(query)
        assert lookback == expected_lookback
        assert length == expected_length

    def test_rejects_below_min_length(self):
        """All candidates have LCS < min_length -> no match."""
        lcs = PathLookbackLCS()
        lcs.add_path("aaaaa.py")          # stem "aaaaa"
        lcs.add_path("bbbbb.py")          # stem "bbbbb"
        # Query "xxxxx.py": LCS with both is 3 (".py")
        lookback, length = lcs.get_lcs("xxxxx.py", min_length=5)
        assert lookback == 0
        assert length == 0

    def test_respects_max_length(self):
        lcs = PathLookbackLCS()
        lcs.add_path("aaaaa.py")
        lookback, length = lcs.get_lcs("bbbbb.py", max_length=2)
        # LCS = 3 (".py") > max_length=2, so filtered out
        assert lookback == 0
        assert length == 0

    def test_picks_larger_length_within_bounds(self):
        """When multiple candidates pass filters, the one with the largest LCS
        is selected."""
        lcs = PathLookbackLCS()
        lcs.add_path("prefix_common_suffix.py")   # idx 0
        lcs.add_path("other_common_suffix.py")    # idx 1
        # Both end with "common_suffix.py"
        lookback, length = lcs.get_lcs("query_common_suffix.py")
        # Level 1 bucket (.py, 'y', 'x'): dict has both paths
        # Reversed: other_common_suffix.py (idx 1, LCS ~) > prefix_common_suffix.py (idx 0)
        assert lookback == 1
        # The common suffix between "query_common_suffix.py" and "other_common_suffix.py"
        # is "_common_suffix.py" = 17 chars (the '_' before 'common' is shared by all three).
        assert length == len("_common_suffix.py")

    def test_length_equals_path_length_short_circuit(self):
        """If LCS of query and a stored path equals query's full length, return
        immediately without checking remaining candidates."""
        lcs = PathLookbackLCS()
        lcs.add_path("aaa.py")
        lcs.add_path("target.py")  # This would give LCS=9 which equals len("target.py")
        lcs.add_path("zzz.py")
        # Query "target.py": LCS with "target.py" = 9 = len("target.py"), short circuit
        lookback, length = lcs.get_lcs("target.py")
        assert lookback == 2  # idx 1, current_index=3 -> 2
        assert length == len("target.py")

    def test_no_match_in_empty_bucket(self):
        """Bucket (suffix, last, lsecond) is empty -> fall through to Level 2."""
        lcs = PathLookbackLCS()
        lcs.add_path("abc.py")            # suffix .py, char='c', lsecond='b'
        # Query has char='x', lsecond='y' -> Level 1 bucket is empty
        lookback, length = lcs.get_lcs("wxy.py")
        # Level 2: ('.py', 'x') empty (abc.py has char='c')
        # Level 3: LCS('.py','.py')=3, abc.py(idx 0) matches via prev_index > best_index
        assert lookback == 1
        assert length == 3


# ---------------------------------------------------------------------------
# Level 2: same (suffix, last), any lsecond
# ---------------------------------------------------------------------------


class TestGetLcsLevel2:
    """Level 2 — query shares suffix and last_char with stored paths but has
    a different lsecond, so the Level 1 bucket is empty.

    V1 Level 2 uses a **fixed length** of ``len(suffix) + len(last)`` (typically
    ``len(suffix) + 1``) rather than computing actual LCS. It picks the
    highest-indexed entry from the matching ``(suffix, last)`` bucket."""

    def test_fallback_same_char_different_lsecond(self):
        lcs = PathLookbackLCS()
        lcs.add_path("aba.py")            # stem "aba", char='a', lsecond='b'
        lcs.add_path("xxb.py")            # stem "xxb", char='b', lsecond='x'
        # Query "ccb.py": char='b', lsecond='c'
        # Level 1: ('.py', 'b', 'c') empty
        # Level 2: ('.py', 'b') bucket -> xxb.py (idx 1)
        #   fixed length = len('.py') + len('b') = 3 + 1 = 4
        lookback, length = lcs.get_lcs("ccb.py")
        assert lookback == 1
        assert length == 4

    def test_fallback_multiple_lsecond_buckets(self):
        lcs = PathLookbackLCS()
        lcs.add_path("aba.py")            # stem "aba", char='a', lsecond='b'
        lcs.add_path("aca.py")            # stem "aca", char='a', lsecond='c'
        # Query "ada.py": stem "ada", char='a', lsecond='d'
        # Level 1: ('.py', 'a', 'd') empty
        # Level 2: ('.py', 'a') has two inner dicts: 'b' -> {aba.py: 0}, 'c' -> {aca.py: 1}
        # For each dict_path, picks the highest index: aba.py(0), aca.py(1)
        # V1 logic: prev_index > best_length (0 initially) — picks first with prev_index > 0
        # So aba.py(0) is skipped (0 > 0 is False), aca.py(1) is selected (1 > 0)
        # best_index=1, best_length=4; lookback=2-1=1
        lookback, length = lcs.get_lcs("ada.py")
        assert lookback == 1
        assert length == 4

    def test_fallback_first_path_with_index_zero(self):
        """Level 2 picks the only candidate even when its index is 0, because
        ``prev_index > best_index`` starts at -1."""
        lcs = PathLookbackLCS()
        lcs.add_path("only.py")           # idx 0, char='y', lsecond='l'
        # Query "xxy.py": char='y', lsecond='x' (different lsecond)
        # Level 1: ('.py', 'y', 'x') empty
        # Level 2: ('.py', 'y') bucket -> only.py(0) -> prev_index=0 > best_index(-1) -> selected
        #   fixed length = 4
        lookback, length = lcs.get_lcs("xxy.py")
        assert lookback == 1
        assert length == 4

    def test_fallback_multiple_char_buckets_level2(self):
        """Level 2 picks the path with the highest index across all
        ``(suffix, last)`` buckets."""
        lcs = PathLookbackLCS()
        lcs.add_path("xa.py")             # idx 0, char='a', lsecond='x'
        lcs.add_path("xxb.py")            # idx 1, char='b', lsecond='x'
        lcs.add_path("xyb.py")            # idx 2, char='b', lsecond='y'
        # Query "zzb.py": char='b', lsecond='z'
        # Level 1: ('.py', 'b', 'z') empty
        # Level 2: ('.py', 'b') -> both xxb.py(1) and xyb.py(2) considered
        #   prev_index=1 > best_index(-1) -> best_index=1
        #   prev_index=2 > best_index(1)   -> best_index=2 (wins)
        # best_index=2 (xyb.py), lookback = 3 - 2 = 1
        lookback, length = lcs.get_lcs("zzb.py")
        assert lookback == 1
        assert length == 4


# ---------------------------------------------------------------------------
# Level 3: same suffix, any char, any lsecond
# ---------------------------------------------------------------------------


class TestGetLcsLevel3:
    """Level 3 — query shares suffix with stored paths but the specific
    ``(suffix, last)`` bucket is empty. V1 picks the suffix in the dict with
    the best LCS to the query suffix, then returns the highest-indexed entry
    from that suffix bucket."""

    def test_fallback_same_extension_new_char(self):
        lcs = PathLookbackLCS()
        lcs.add_path("aaaa.py")
        lcs.add_path("bbbb.py")
        # Query "xxxx.py": char='x', lsecond='x'
        # Level 1: ('.py', 'x', 'x') empty
        # Level 2: ('.py', 'x') empty (no char='x' bucket)
        # Level 3: iterates suffixes, finds '.py' with LCS suffix('.py', '.py')=3
        # Then iterates all (char, lsecond) buckets under '.py':
        #   'a'/'a': aaaa.py(0), 'b'/'b': bbbb.py(1)
        # prev_index=0 > best_index(-1) -> best_index=0
        # prev_index=1 > best_index(0)  -> best_index=1 (wins)
        lookback, length = lcs.get_lcs("xxxx.py")
        # Level 3 picks the highest-indexed entry: bbbb.py(idx 1)
        assert lookback == 1
        assert length == 3

    def test_fallback_when_high_enough_index(self):
        """Level 3 returns a result when a stored path has an index greater
        than the best suffix-LCS length."""
        lcs = PathLookbackLCS()
        # Add 5 paths so the last one has index=4 > best_length=3
        lcs.add_path("a.py")              # idx 0
        lcs.add_path("b.py")              # idx 1
        lcs.add_path("c.py")              # idx 2
        lcs.add_path("d.py")              # idx 3
        lcs.add_path("e.py")              # idx 4
        # Query "z.py": char='z', lsecond=''
        # Level 1: ('.py', 'z', '') empty
        # Level 2: ('.py', 'z') empty
        # Level 3: suffix LCS('.py', '.py')=3 -> best_length=3
        # Iterates all buckets:
        #   'a'/l2='': a.py(0) prev_index=0 > 3? No
        #   'b'/l2='': b.py(1) prev_index=1 > 3? No
        #   'c'/l2='': c.py(2) prev_index=2 > 3? No
        #   'd'/l2='': d.py(3) prev_index=3 > 3? No
        #   'e'/l2='': e.py(4) prev_index=4 > 3? Yes! best_index=4
        # lookback = 5 - 4 = 1
        lookback, length = lcs.get_lcs("z.py")
        assert lookback == 1
        assert length == 3

    def test_fallback_multiple_suffixes(self):
        """When multiple suffixes exist, the one with the highest LCS to the
        query suffix is selected."""
        lcs = PathLookbackLCS()
        lcs.add_path("data.txt")          # suffix .txt
        lcs.add_path("info.txt")          # suffix .txt
        lcs.add_path("main.py")           # suffix .py
        # Query "query.md": suffix '.md'
        # Level 1: ('.md', 'd', '')... wait, get_key("query.md"): path="query", dot=".", suffix="md"
        #   suffix = ".md", last = "y", second = "r"
        # Actually let me trace: "query.md".rpartition('.') = ("query", ".", "md")
        #   suffix = f'.{"md"}' = ".md"
        #   last = "y", second = "r"
        # Level 1: ('.md', 'y', 'r') empty
        # Level 2: ('.md', 'y') empty
        # Level 3: compare suffix LCS('.md', '.txt') vs LCS('.md', '.py')
        #   '.md' vs '.txt': suffix LCS = '' (0)
        #   '.md' vs '.py': suffix LCS = '' (0)
        # All 0, so best_length = 0 -> no match
        lookback, length = lcs.get_lcs("query.md")
        assert lookback == 0
        assert length == 0

    def test_fallback_partial_suffix_match(self):
        """Suffixes that share a common suffix get matched."""
        lcs = PathLookbackLCS()
        # Add many paths so indices are high enough
        for i in range(6):
            lcs.add_path(f"file{i}.tar.gz")   # suffix .tar.gz
        # Query with suffix that partially matches .tar.gz
        # get_key("foo.gz"): path="foo", suffix=".gz", last="o", second="o"
        # Level 1: ('.gz', 'o', 'o') empty
        # Level 2: ('.gz', 'o') empty
        # Level 3: LCS('.gz', '.tar.gz') = '.gz' = 3
        #   best_length = 3
        #   Iterates file*.tar.gz buckets: last indices 0-5
        #   file5.tar.gz has prev_index=5 > 3 -> selected
        # But wait, the suffixes need to match. Suffix is '.tar.gz', not '.gz'.
        # Actually, get_key("file0.tar.gz"): "file0.tar.gz".rpartition('.') = ("file0.tar", ".", "gz")
        #   suffix = ".gz", not ".tar.gz"
        # So all have suffix = ".gz". Level 3 LCS('.gz', '.gz') = 3.
        lookback, length = lcs.get_lcs("foo.gz")
        assert lookback == 1
        assert length == 3


# ---------------------------------------------------------------------------
# Tie-breaking: smaller lookback when same LCS length
# ---------------------------------------------------------------------------


class TestGetLcsTieBreak:
    """When multiple candidates in the same bucket have equal LCS length,
    V1's reverse iteration picks the most recent one (smaller lookback)."""

    def test_tie_two_candidates_same_bucket(self):
        """Two paths in same bucket with equal LCS — the more recent wins."""
        lcs = PathLookbackLCS()
        lcs.add_path("aaa_common.py")          # idx 0, LCS="_common.py"=10
        lcs.add_path("bbb_common.py")          # idx 1, LCS="_common.py"=10
        lookback, length = lcs.get_lcs("ccc_common.py")
        # Bucket ('.py', 'y', 'n'): dict reversed -> bbb_common.py(1), then aaa_common.py(0)
        # bbb_common.py(1): LCS=10 -> best_index=1, best_length=10
        # aaa_common.py(0): LCS=10, not > 10 -> skip
        assert lookback == 1  # current_index=2, matched idx 1
        assert length == 10

    def test_tie_three_candidates_same_bucket(self):
        """Three paths in same bucket with equal LCS — the most recent wins."""
        lcs = PathLookbackLCS()
        for i in range(3):
            lcs.add_path(f"prefix_{i}_suffix.py")
        lookback, length = lcs.get_lcs("query_suffix.py")
        # All in bucket ('.py', 'y', 'x'), LCS="_suffix.py"=7
        # reversed: idx 2 -> best_index=2, then idx 1 (not >), then idx 0 (not >)
        assert lookback == 1  # current_index=3, matched idx 2
        assert length == len("_suffix.py")

    def test_tie_same_suffix_same_bucket(self):
        """Paths in same bucket with equal LCS — most recent wins."""
        lcs = PathLookbackLCS()
        lcs.add_path("target_a.py")    # idx 0, suffix .py
        lcs.add_path("other.py")       # idx 1
        lcs.add_path("target_b.py")    # idx 2, suffix .py
        lookback, length = lcs.get_lcs("target_z.py")
        # Both target_a.py(0) and target_b.py(2) are in bucket ('.py', 'y', 'r')
        # reversed: target_b.py(2), target_a.py(0)
        # target_b.py(2): LCS(".py")=3 -> best_index=2, best_length=3
        # target_a.py(0): LCS(".py")=3, not > 3 -> skip
        assert lookback == 1  # current_index=3, matched idx 2
        assert length == 3


# ---------------------------------------------------------------------------
# No match at any level
# ---------------------------------------------------------------------------


class TestGetLcsNoMatch:
    """No match found at any level -> (0, 0)."""

    def test_no_paths(self):
        lcs = PathLookbackLCS()
        assert lcs.get_lcs("anything.py") == (0, 0)

    def test_different_extension(self):
        lcs = PathLookbackLCS()
        lcs.add_path("data.txt")
        assert lcs.get_lcs("script.py") == (0, 0)

    def test_different_extension_multiple(self):
        lcs = PathLookbackLCS()
        lcs.add_path("data.txt")
        lcs.add_path("info.txt")
        assert lcs.get_lcs("main.py") == (0, 0)

    def test_empty_query_with_stored_paths(self):
        lcs = PathLookbackLCS()
        lcs.add_path("file.py")
        lookback, length = lcs.get_lcs("")
        # get_key(""): path="", suffix="", last="", second=""
        # Level 1: dict_suffix[""][""][""] -> empty -> no match
        # Level 2: suffix="" -> iterate suffixes: (".py", etc)
        #   cand_suffix ("") != suffix (".py") -> skip
        # Level 3: LCS("", ".py") = 0 -> best_length = 0 -> no match
        assert lookback == 0
        assert length == 0


# ---------------------------------------------------------------------------
# min_length / max_length filters
# ---------------------------------------------------------------------------


class TestGetLcsMinMaxLength:
    """Test the ``min_length`` and ``max_length`` filtering parameters."""

    def test_min_length_excludes_shorter(self):
        lcs = PathLookbackLCS()
        lcs.add_path("aaaaa.py")          # idx 0
        lcs.add_path("bbbbb.py")          # idx 1
        # LCS of "xxxxx.py" with stored paths = 3 (".py")
        lookback, length = lcs.get_lcs("xxxxx.py", min_length=5)
        assert lookback == 0
        assert length == 0

    def test_min_length_allows_equal(self):
        lcs = PathLookbackLCS()
        lcs.add_path("aaaaa.py")               # idx 0
        lookback, length = lcs.get_lcs("bbbbb.py", min_length=3)
        # Level 3: LCS('.py','.py')=3 >= min_length=3, aaaaa.py(0) matched
        assert lookback == 1
        assert length == 3

    def test_min_length_allows_longer(self):
        lcs = PathLookbackLCS()
        lcs.add_path("prefix_suffix.py")
        # LCS("other_suffix.py", "prefix_suffix.py") = "_suffix.py" = 10
        lookback, length = lcs.get_lcs("other_suffix.py", min_length=5)
        assert lookback == 1
        assert length >= 5

    def test_max_length_excludes_longer(self):
        lcs = PathLookbackLCS()
        lcs.add_path("aaaaa.py")
        lookback, length = lcs.get_lcs("bbbbb.py", max_length=2)
        # Level 3: LCS('.py','.py')=3 > max_length=2, suffix filtered
        assert lookback == 0
        assert length == 0

    def test_max_length_allows_equal(self):
        lcs = PathLookbackLCS()
        lcs.add_path("aaaaa.py")               # idx 0
        lookback, length = lcs.get_lcs("bbbbb.py", max_length=3)
        # Level 3: LCS('.py','.py')=3 <= max_length=3, aaaaa.py(0) matched
        assert lookback == 1
        assert length == 3

    def test_max_length_allows_shorter(self):
        lcs = PathLookbackLCS()
        lcs.add_path("long_ending.py")         # idx 0
        lookback, length = lcs.get_lcs("short.py", max_length=10)
        # Level 3: LCS('.py','.py')=3 <= max_length=10, matched
        assert lookback == 1
        assert length <= 10

    def test_min_and_max_together(self):
        lcs = PathLookbackLCS()
        lcs.add_path("aaaaa.py")               # idx 0
        lookback, length = lcs.get_lcs("bbbbb.py", min_length=3, max_length=3)
        # Level 3: LCS('.py','.py')=3 passes both bounds, matched
        assert lookback == 1
        assert length == 3

    def test_min_and_max_exclude_all(self):
        lcs = PathLookbackLCS()
        lcs.add_path("aaaaa.py")
        lcs.add_path("bbbbb.py")
        lookback, length = lcs.get_lcs("xxxxx.py", min_length=10, max_length=20)
        assert lookback == 0
        assert length == 0

    def test_max_length_at_level2(self):
        """max_length can filter the fixed-length result from Level 2."""
        lcs = PathLookbackLCS()
        lcs.add_path("abc.py")            # idx 0, char='c', lsecond='b'
        # Query "xbc.py": char='c', lsecond='b' -> Level 1 bucket exists
        # But let's make Level 1 miss: different lsecond
        lcs.add_path("def.py")            # idx 1, char='f', lsecond='e'
        # Query "xyz.py": char='z', lsecond='y'
        # Level 1: ('.py', 'z', 'y') empty
        # Level 2: ('.py', 'z') empty (no char='z')
        # Falls to Level 3
        lookback, length = lcs.get_lcs("xyz.py", max_length=2)
        assert lookback == 0
        assert length == 0


# ---------------------------------------------------------------------------
# Lookback distance
# ---------------------------------------------------------------------------


class TestLookbackDistance:
    """Verify that the lookback (1-based distance to matched path) is computed
    correctly based on the internal index counter."""

    def test_lookback_increases_with_more_paths(self):
        lcs = PathLookbackLCS()
        lcs.add_path("base.py")           # idx 0
        lcs.add_path("unrelated.py")      # idx 1
        lcs.add_path("unrelated2.py")     # idx 2
        # Query matches base.py (idx 0), current_index=3 -> lookback=3
        lookback, length = lcs.get_lcs("base.py")
        assert lookback == 3

    def test_lookback_adjacent(self):
        lcs = PathLookbackLCS()
        lcs.add_path("prev.py")           # idx 0
        lcs.add_path("current.py")        # idx 1
        lookback, length = lcs.get_lcs("current.py")
        assert lookback == 1

    def test_lookback_same_path_twice(self):
        lcs = PathLookbackLCS()
        lcs.add_path("file.py")           # idx 0
        lcs.add_path("file.py")           # idx 1 (overwrites)
        lookback, length = lcs.get_lcs("file.py")
        # The dict has file.py -> 1, current_index=2 -> lookback=1
        assert lookback == 1

    def test_lookback_with_mixed_adds(self):
        lcs = PathLookbackLCS()
        lcs.add_path("a.py")              # idx 0
        lcs.add_path("b.txt")             # idx 1
        lcs.add_path("c.py")              # idx 2
        lcs.add_path("d.py")              # idx 3
        lookback, length = lcs.get_lcs("a.py")
        # Exact match short circuit -> lookback = current_index - prev_index = 4 - 0 = 4
        assert lookback == 4


# ---------------------------------------------------------------------------
# Integration / combined scenarios
# ---------------------------------------------------------------------------


class TestIntegration:
    """End-to-end scenarios mixing multiple additions and queries."""

    def test_sequential_adds_and_queries(self):
        lcs = PathLookbackLCS()
        assert lcs.get_lcs("first.py") == (0, 0)

        lcs.add_path("first.py")
        lookback, length = lcs.get_lcs("first.py")
        assert lookback == 1
        assert length == len("first.py")

        lcs.add_path("second.py")
        # Now query "first.py" again
        lookback, length = lcs.get_lcs("first.py")
        assert lookback == 2  # idx 0, current_index=2 -> 2
        assert length == len("first.py")

    def test_multiple_extensions(self):
        lcs = PathLookbackLCS()
        lcs.add_path("data.txt")
        lcs.add_path("main.py")
        lcs.add_path("notes.txt")

        # Query "other.txt": same extension .txt
        lookback, length = lcs.get_lcs("other.txt")
        # Level 1: ('.txt', 'r', 'e') empty (data.txt has last='a', notes.txt has last='s')
        # Level 2: ('.txt', 'r') empty (no char='r' in .txt)
        # Level 3: LCS('.txt', '.txt') = 4 -> best_length=4
        # Iterates .txt buckets: data.txt(0), notes.txt(1)
        # Level 3 picks the highest-indexed entry: notes.txt(idx 1)
        assert lookback == 1
        assert length == 4

    def test_mixed_queries_after_multiple_adds(self):
        lcs = PathLookbackLCS()
        lcs.add_path("project_a/data.py")   # idx 0
        lcs.add_path("project_b/data.py")   # idx 1
        lcs.add_path("project_c/main.py")   # idx 2

        # Query "project_a/data.py": exact match with idx 0
        lookback, length = lcs.get_lcs("project_a/data.py")
        assert lookback == 3
        assert length == len("project_a/data.py")

        # Query "project_d/data.py": same stem "data", char='a', lsecond='t'
        # Level 1: ('.py', 'a', 't') has both data.py(0) and data.py(1)
        #   Reversed: project_b/data.py(1) LCS=15?
        #   "project_d/data.py" vs "project_b/data.py": LCS = "a/data.py" = 8?
        # Actually: "project_d/data.py" ends with "/data.py" and "project_b/data.py" ends with "/data.py"
        # The LCS of full paths: "a/data.py"? Let me compute exactly.
        # "project_d/data.py" vs "project_b/data.py":
        #   common suffix: "/data.py" = 8 chars (/, d, a, t, a, ., p, y)
        #   Actually "/data.py" reversed: y,p,.,a,t,a,d,/ - yes 8 chars
        #   Wait: "project_b/data.py" length = 17, "project_d/data.py" length = 17
        #   reversed: y,p,.,a,t,a,d,/ vs y,p,.,a,t,a,d,/ -> all 8 match? No:
        #   "project_b/data.py"[-8:] = "/data.py"? "project_b/data.py" = p-r-o-j-e-c-t-_-b-/-d-a-t-a-.-p-y
        #   No that's not right. Let me just use the actual chars:
        #   "project_b/data.py": p r o j e c t _ b / d a t a . p y (18 chars)
        #   "project_d/data.py": p r o j e c t _ d / d a t a . p y (18 chars)
        #   Reversed: y p . a t a d / b _ t c e j o r p
        #             y p . a t a d / d _ t c e j o r p
        #   Compare: y=y, p=p, .=., a=a, t=t, a=a, d=d, /=/, b!=d -> LCS length = 8
        #   So length=8, best_length=8, best_index=1
        #   lookback = 3 - 1 = 2
        lookback, length = lcs.get_lcs("project_d/data.py")
        assert lookback == 2
        assert length == 8  # "/data.py"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary and pathological inputs."""

    def test_empty_string_path(self):
        lcs = PathLookbackLCS()
        lcs.add_path("")                   # idx 0
        # get_key(""): path="", suffix="", last="", second=""
        # Level 1: dict_suffix[""][""][""] = {"": 0}
        # LCS("", "") = 0 < min_length(1 default), so Level 1 filters it out
        # Level 2/3: suffix "" has length 0, no match
        lookback, length = lcs.get_lcs("")
        assert lookback == 0
        assert length == 0

    def test_path_with_only_extension(self):
        """A path that is just a file extension like ``.gitignore``."""
        lcs = PathLookbackLCS()
        lcs.add_path(".gitignore")
        # get_key(".gitignore"): rpartition('.') = ("", ".", "gitignore")
        #   suffix = ".gitignore"
        #   path = "" -> last = "", second = ""
        assert lcs.dict_suffix[".gitignore"][""][""][".gitignore"] == 0

        # Query ".gitignore": exact match
        lookback, length = lcs.get_lcs(".gitignore")
        assert lookback == 1
        assert length == len(".gitignore")

    def test_path_with_trailing_dot(self):
        """A path like ``file.`` where last char after dot is empty."""
        lcs = PathLookbackLCS()
        lcs.add_path("file.")
        # rpartition('.'): ("file", ".", "") -> suffix = ".", path="file"
        # last = "e", second = "l"
        pass  # just ensure no crash

    def test_unicode_paths(self):
        lcs = PathLookbackLCS()
        lcs.add_path("数据/文件.py")
        lcs.add_path("备份/文件.py")
        lookback, length = lcs.get_lcs("新建/文件.py")
        # Both stored paths end with "/文件.py"
        # LCS of "新建/文件.py" with either stored path:
        # common suffix = "/文件.py" = 6 chars (includes '/')
        # Level 1: ('.py', '件', '文') bucket has both entries
        # Reversed: 备份/文件.py(1), 数据/文件.py(0)
        # best_index=1, best_length=6
        assert lookback == 1
        assert length == 6

    def test_single_char_stem(self):
        lcs = PathLookbackLCS()
        lcs.add_path("a.py")               # stem "a", char='a', lsecond=''
        lcs.add_path("b.py")               # stem "b", char='b', lsecond=''
        # Query "c.py": char='c', lsecond=''
        # Level 1: ('.py', 'c', '') empty
        # Level 2: ('.py', 'c') empty
        # Level 3: LCS('.py', '.py') = 3 -> best_length=3
        # Iterates 'a'/l2='': a.py(0) prev_index=0 > best_index(-1) -> index=0
        #   'b'/l2='': b.py(1) prev_index=1 > best_index(0) -> index=1 (wins)
        lookback, length = lcs.get_lcs("c.py")
        assert lookback == 1
        assert length == 3

    def test_very_long_paths(self):
        """Long paths should not cause issues."""
        long_a = "a" * 1000 + ".py"
        long_b = "b" * 1000 + ".py"
        lcs = PathLookbackLCS()
        lcs.add_path(long_a)                    # idx 0
        lookback, length = lcs.get_lcs(long_b)
        # Level 3: LCS('.py','.py')=3, long_a(0) matched
        assert lookback == 1
        assert length == 3

    def test_min_length_zero(self):
        """min_length=0 should allow any match (including empty LCS)."""
        lcs = PathLookbackLCS()
        lcs.add_path("data.txt")
        lcs.add_path("main.py")
        # Query "other.txt": same suffix .txt
        # Level 1: ('.txt', 'r', 'e') empty (data.txt has last='a')
        # Level 2: ('.txt', 'r') empty
        # Level 3: LCS('.txt', '.txt') = 4 -> best_length=4
        # data.txt(0): prev_index=0 > best_index(-1) -> matched
        lookback, length = lcs.get_lcs("other.txt", min_length=0)
        assert lookback == 2
        assert length == 4


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------


class TestRegression:
    """Regression tests for known edge cases and bugs."""

    def test_level2_picks_highest_index(self):
        """Level 3 picks the highest-indexed entry from the matching suffix."""
        lcs = PathLookbackLCS()
        lcs.add_path("a.py")              # idx 0, char='a'
        lcs.add_path("b.py")              # idx 1, char='b'
        lcs.add_path("c.py")              # idx 2, char='c'
        # Query "d.py": char='d', lsecond=''
        # Level 1: ('.py', 'd', '') empty
        # Level 2: ('.py', 'd') empty
        # Level 3: LCS('.py','.py')=3, picks c.py(idx 2)
        lookback, length = lcs.get_lcs("d.py")
        assert lookback == 1
        assert length == 3

    def test_level1_empty_dict_no_crash(self):
        """An empty Level-1 bucket should not cause errors."""
        lcs = PathLookbackLCS()
        # dict_suffix[".py"]["z"]["z"] is auto-created but empty
        _ = lcs.dict_suffix[".py"]["z"]["z"]
        lookback, length = lcs.get_lcs("test.py")
        assert lookback == 0
        assert length == 0

    def test_add_path_then_query_same_bucket(self):
        """Verify correct index tracking across add/get_lcs interleaving."""
        lcs = PathLookbackLCS()
        lcs.add_path("first.py")          # idx 0
        lookback, length = lcs.get_lcs("second.py")  # current_index=1
        # Level 1: ('.py', 'd', 'n') empty (first.py has last='t', second='s')
        # Level 2: ('.py', 'd') empty
        # Level 3: LCS('.py', '.py')=3 -> best_length=3
        # first.py(0): prev_index=0 > best_index(-1) -> matched
        assert lookback == 1
        assert length == 3

    def test_level2_selects_index_zero(self):
        """Level 2 selects the only candidate even when its index is 0,
        because ``prev_index > best_index`` starts at -1."""
        lcs = PathLookbackLCS()
        lcs.add_path("onlypath.py")       # idx 0, last='h', lsecond='t'
        # Query "newbash.py": last='h', lsecond='s' (different lsecond)
        # Level 1: ('.py', 'h', 's') empty
        # Level 2: ('.py', 'h') -> onlypath.py(0) -> prev_index=0 > best_index(-1) -> selected
        lookback, length = lcs.get_lcs("newbash.py")
        assert lookback == 1
        assert length == 4

    def test_defaultdict_side_effect_dotfile_lcs(self):
        """Regression: V1's ``get_lcs`` must not auto-create a defaultdict entry
        for the query suffix.  Level 1 accesses ``self.dict_suffix[suffix]`` which
        creates an empty bucket for dotfiles like ``.prettierignore``.  Level 3's
        suffix-LCS loop then picks this empty bucket (LCS = len(suffix)) over a
        real bucket such as ``.gitignore`` / ``ignore`` → (0, 0) instead of a valid
        match.

        Reference (V3) result for the same inputs is ``lookback=1, length=6``.
        """
        lcs = PathLookbackLCS()
        lcs.add_path('.gitignore')          # idx 0, suffix='.gitignore'
        lcs.add_path('some_other.py')       # idx 1
        lcs.add_path('webapp/.gitignore')   # idx 2, suffix='.gitignore'

        lookback, length = lcs.get_lcs('.prettierignore', min_length=3, max_length=63)
        # Must match V3 behaviour: LCS('.prettierignore', '.gitignore') = 6
        assert lookback == 1
        assert length == 6


# ---------------------------------------------------------------------------
# max_lookback filter
# ---------------------------------------------------------------------------


class TestGetLcsMaxLookback:
    """Test the ``max_lookback`` parameter that limits forward search distance.

    The lookback of a candidate is ``current_index - prev_index``.
    ``max_lookback`` filters out candidates whose lookback exceeds this value.
    """

    def test_default_no_filtering(self):
        """max_lookback=None (default) behaves identically to no limit."""
        lcs = PathLookbackLCS()
        lcs.add_path("a.py")       # idx 0
        lcs.add_path("b.py")       # idx 1
        lcs.add_path("c.py")       # idx 2
        lookback, length = lcs.get_lcs("d.py", max_lookback=None)
        # Level 3: LCS('.py','.py')=3, c.py(idx 2) matched
        assert lookback == 1
        assert length == 3

    # ------------------------------------------------------------------
    # Level 1
    # ------------------------------------------------------------------

    def test_level1_filters_beyond_max_lookback(self):
        """Level 1 skips candidates whose lookback exceeds max_lookback."""
        lcs = PathLookbackLCS()
        # All paths share bucket (.py, 'a', 'a')
        lcs.add_path("xaaa.py")    # idx 0
        lcs.add_path("xbaa.py")    # idx 1
        lcs.add_path("xcaa.py")    # idx 2
        # Query "xdaa.py": same bucket, max_lookback=1
        # reversed: xcaa.py(2, lookback=1) ok, xbaa.py(1, lookback=2) break early
        lookback, length = lcs.get_lcs("xdaa.py", max_lookback=1)
        assert lookback == 1
        # LCS("xdaa.py", "xcaa.py") = "aa.py" = 5
        assert length == 5

    def test_level1_all_candidates_beyond_lookback_falls_through(self):
        """All Level 1 candidates exceed max_lookback -> fall through to Level 2/3."""
        lcs = PathLookbackLCS()
        lcs.add_path("xaaa.py")    # idx 0, bucket (.py, 'a', 'a')
        lcs.add_path("xbaa.py")    # idx 1, bucket (.py, 'a', 'a')
        # Query "xcaa.py": same bucket
        # max_lookback=0: most recent is xbaa.py(1, lookback=1) > 0 -> break immediately
        # No Level 1 result. Level 2: suffix '.py', last 'a' -> xbaa.py(1) filtered too
        # Level 3: suffix '.py' -> xbaa.py(1) filtered -> (0, 0)
        lookback, length = lcs.get_lcs("xcaa.py", max_lookback=0)
        assert lookback == 0
        assert length == 0

    def test_level1_exact_match_within_lookback_short_circuits(self):
        """Exact match within max_lookback triggers short-circuit return."""
        lcs = PathLookbackLCS()
        lcs.add_path("xaaa.py")    # idx 0
        lcs.add_path("xbaa.py")    # idx 1
        lcs.add_path("xcaa.py")    # idx 2
        # Query "xbaa.py": exact match with idx 1, lookback=3-1=2
        # max_lookback=2: xcaa.py(2, lookback=1) checked, not full match
        #                xbaa.py(1, lookback=2) full match -> short circuit
        lookback, length = lcs.get_lcs("xbaa.py", max_lookback=2)
        assert lookback == 2
        assert length == len("xbaa.py")

    def test_level1_exact_match_beyond_lookback_no_short_circuit(self):
        """Exact match beyond max_lookback does not short circuit; a nearer
        candidate may still match."""
        lcs = PathLookbackLCS()
        lcs.add_path("xaaa.py")    # idx 0
        lcs.add_path("xbaa.py")    # idx 1, the exact target
        lcs.add_path("xcaa.py")    # idx 2, most recent
        # Query "xbaa.py": exact match with idx 1, lookback=3-1=2
        # max_lookback=1: xcaa.py(2, lookback=1) ok — LCS("xbaa.py","xcaa.py")="aa.py"=5
        #                  xbaa.py(1, lookback=2) filtered — break early
        # Result: xcaa.py matched with LCS=5
        lookback, length = lcs.get_lcs("xbaa.py", max_lookback=1)
        assert lookback == 1
        assert length == 5

    # ------------------------------------------------------------------
    # Level 2
    # ------------------------------------------------------------------

    def test_level2_filters_beyond_max_lookback(self):
        """Level 2 filters candidates whose lookback exceeds max_lookback."""
        lcs = PathLookbackLCS()
        # Same suffix, same last char, different lsecond -> Level 1 misses, Level 2 hits
        lcs.add_path("xabx.py")    # idx 0, last='x', second='b', bucket (.py, 'x', 'b')
        lcs.add_path("xacx.py")    # idx 1, last='x', second='c', bucket (.py, 'x', 'c')
        # Query "xadx.py": last='x', second='d' -> Level 1 miss
        # Level 2: suffix '.py', last 'x':
        #   lsecond='b': xabx.py(0), lookback=2-0=2 > 1 -> filtered
        #   lsecond='c': xacx.py(1), lookback=2-1=1 <= 1 -> selected, best_length=4
        lookback, length = lcs.get_lcs("xadx.py", max_lookback=1)
        assert lookback == 1
        assert length == 4

    def test_level2_all_candidates_beyond_lookback_falls_through(self):
        """All Level 2 candidates exceed max_lookback -> fall through to Level 3."""
        lcs = PathLookbackLCS()
        lcs.add_path("xabx.py")    # idx 0
        lcs.add_path("xacx.py")    # idx 1
        # Query "xadx.py": max_lookback=0 filters both Level 2 candidates
        # Level 3: LCS('.py','.py')=3
        #   xacx.py(1): lookback=1 > 0 -> filtered
        #   xabx.py(0): lookback=2 > 0 -> filtered
        lookback, length = lcs.get_lcs("xadx.py", max_lookback=0)
        assert lookback == 0
        assert length == 0

    # ------------------------------------------------------------------
    # Level 3
    # ------------------------------------------------------------------

    def test_level3_filters_beyond_max_lookback(self):
        """Level 3 filters candidates whose lookback exceeds max_lookback."""
        lcs = PathLookbackLCS()
        lcs.add_path("aaaa.py")    # idx 0, last='a', bucket (.py, 'a', 'a')
        # Query "bbbb.py": last='b', lsecond='b'
        # Level 1: (.py, 'b', 'b') empty
        # Level 2: (.py, 'b') empty
        # Level 3: LCS('.py','.py')=3, aaaa.py(0): lookback=1-0=1 <= 1 -> matched
        lookback, length = lcs.get_lcs("bbbb.py", max_lookback=1)
        assert lookback == 1
        assert length == 3

    def test_level3_all_candidates_beyond_lookback_falls_through(self):
        """All Level 3 candidates exceed max_lookback -> (0, 0)."""
        lcs = PathLookbackLCS()
        lcs.add_path("aaaa.py")    # idx 0
        # Query "bbbb.py": max_lookback=0, aaaa.py(0) lookback=1 > 0 -> filtered
        lookback, length = lcs.get_lcs("bbbb.py", max_lookback=0)
        assert lookback == 0
        assert length == 0

    # ------------------------------------------------------------------
    # Combinations with other parameters
    # ------------------------------------------------------------------

    def test_combined_with_min_length(self):
        """max_lookback and min_length both apply — filters at all levels."""
        lcs = PathLookbackLCS()
        lcs.add_path("xaaa.py")    # idx 0, bucket (.py, 'a', 'a')
        lcs.add_path("xbaa.py")    # idx 1
        lcs.add_path("xcaa.py")    # idx 2
        # Query "xdaa.py": same bucket
        # Level 1: LCS=5 < min_length=6 -> filtered, break (next beyond lookback)
        # Level 2: fixed length=4 < min_length=6 -> exit check fails
        # Level 3: suffix LCS('.py','.py')=3 < min_length=6 -> exit check fails
        lookback, length = lcs.get_lcs("xdaa.py", min_length=6, max_lookback=1)
        assert lookback == 0
        assert length == 0

    def test_combined_with_max_length(self):
        """max_lookback and max_length both apply — filters at all levels."""
        lcs = PathLookbackLCS()
        lcs.add_path("xaaa.py")    # idx 0, bucket (.py, 'a', 'a')
        lcs.add_path("xbaa.py")    # idx 1
        lcs.add_path("xcaa.py")    # idx 2
        # Query "xdaa.py": same bucket
        # Level 1: LCS=5 > max_length=2 -> filtered
        # Level 2: fixed length=4 > max_length=2 -> filtered
        # Level 3: suffix LCS('.py','.py')=3 > max_length=2 -> no suffix match
        lookback, length = lcs.get_lcs("xdaa.py", max_length=2, max_lookback=1)
        assert lookback == 0
        assert length == 0

    def test_multiple_candidates_within_lookback_picks_best_lcs(self):
        """When multiple candidates are within max_lookback, pick the one
        with the largest LCS."""
        lcs = PathLookbackLCS()
        # Same bucket suffixed with "__common.py": last='y', second='n'
        lcs.add_path("zz__common.py")    # idx 0
        lcs.add_path("yy__common.py")    # idx 1
        # Query "xx__common.py": same bucket
        # Both candidates are within max_lookback=2.
        # LCS("xx__common.py", "yy__common.py") = "__common.py" = 12
        # Tie goes to the most recent (idx 1).
        lookback, length = lcs.get_lcs("xx__common.py", max_lookback=2)
        assert lookback == 1
        assert length == len("__common.py")


# ---------------------------------------------------------------------------
# Real-world regression: call-site input consistency (not a PathLookbackLCS bug)
# ---------------------------------------------------------------------------


class TestRealWorldSuffixReuse:
    """Regression tests from production pack encoding.

    ``encode_base.py iter_index_data()`` was observed emitting ``N png 0 0``
    (no suffix reuse) for high-frequency extensions like ``.png``:

        assets/character/Firefly.2.png 18 irefly 6 13
        assets/character/Firefly.png   25 png    0 0

    The root causes were fixed in two places:
    - call site (encode_base.py): ``get_lcs()`` now queries the full path,
      consistent with ``add_path()`` and with the decoder, which takes
      suffixes from full lookback paths;
    - PathLookbackLCS itself: ``get_key()`` no longer clears the stem of a
      dot-less path, and Level 3 compares a dot-less query path against the
      bucket suffix, so a stripped path like ``"png"`` still finds the
      ``('.png', ...)`` bucket.

    These tests feed full paths to both methods — the contract the decoder
    (``decode_base._decode_paths``) relies on — and assert the class matches
    correctly.
    """

    @pytest.mark.parametrize("paths, query, expected", [
        # Multi-dot basename pair: LCP of the two full paths stops right before
        # the final dot, so a prefix-stripped query would be "png" (no dot).
        # With consistent full-path input the suffix ".png" is reused.
        (["assets/character/Firefly.2.png"], "assets/character/Firefly.png", (1, 4)),
        (["assets/cn/assignment/dispatch/ASSIGNMENT_START.SEARCH.png"],
         "assets/cn/assignment/dispatch/ASSIGNMENT_START.png", (1, 4)),
        # Same-stem different-extension pair: ".bmp" and ".png" suffixes differ,
        # no cross-suffix match is expected by design.
        (["f/foo.bmp"], "f/foo.png", (0, 0)),
        # Same-stem pair after earlier ".png" files: matches the nearest ".png"
        # bucket (Level 3 suffix match), lookback spans the ".bmp" entry.
        (["a/1.png", "b/2.png", "f/foo.bmp"], "f/foo.png", (2, 4)),
    ])
    def test_consistent_full_path_input(self, paths, query, expected):
        lcs = PathLookbackLCS()
        for path in paths:
            lcs.add_path(path)
        assert lcs.get_lcs(query, min_length=3) == expected

    def test_stripped_query_matches_same_suffix_bucket(self):
        """A dot-less stripped query (e.g. "png" from ".png") still matches:
        Level 3 compares the path itself against bucket suffixes, so the
        ('.png', ...) bucket of a stored full path is found."""
        lcs = PathLookbackLCS()
        lcs.add_path("assets/character/Firefly.2.png")
        # "png" is the prefix-stripped form of "assets/character/Firefly.png";
        # LCS("png", ".png") == 3 >= min_length, matched via Level 3
        lookback, length = lcs.get_lcs("png", min_length=3)
        assert lookback == 1
        assert length == 3
