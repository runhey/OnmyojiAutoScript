"""
Tests for ``oas.ext.algorithm.pathlcs_v3.PathLookbackLCSV3``.

V3 stores all paths in a flat list and does a linear scan. No bucketing,
no key extraction, no fallback levels — every call compares the query against
every previously stored path.
"""

from oas.ext.algorithm.pathlcs_v3 import PathLookbackLCSV3

# ---------------------------------------------------------------------------
# Tests for add_path()
# ---------------------------------------------------------------------------


class TestAddPath:
    """PathLookbackLCSV3.add_path() stores paths in a flat list."""

    def test_add_first_path(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("foo.py")
        assert lcs.index == 1
        assert lcs.paths == ["foo.py"]

    def test_add_multiple_paths(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("a.py")
        lcs.add_path("b.py")
        lcs.add_path("c.py")
        assert lcs.index == 3
        assert lcs.paths == ["a.py", "b.py", "c.py"]

    def test_add_duplicate_path(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("foo.py")
        lcs.add_path("foo.py")
        assert lcs.paths == ["foo.py", "foo.py"]
        assert lcs.index == 2

    def test_add_empty_string(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("")
        assert lcs.paths == [""]
        assert lcs.index == 1


# ---------------------------------------------------------------------------
# Tests for get_lcs() — no match
# ---------------------------------------------------------------------------


class TestGetLcsNoMatch:
    """No match found -> (0, 0)."""

    def test_no_paths(self):
        lookback, length = PathLookbackLCSV3().get_lcs("anything.py")
        assert lookback == 0
        assert length == 0

    def test_empty_query_no_paths(self):
        lookback, length = PathLookbackLCSV3().get_lcs("")
        assert lookback == 0
        assert length == 0

    def test_empty_query_with_stored_paths(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("file.py")
        # LCS("", "file.py") = 0 < min_length=1
        lookback, length = lcs.get_lcs("")
        assert lookback == 0
        assert length == 0

    def test_different_extension(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("data.txt")
        # LCS("script.py", "data.txt") = 0 < min_length=1
        lookback, length = lcs.get_lcs("script.py")
        assert lookback == 0
        assert length == 0

    def test_different_extension_multiple(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("data.txt")
        lcs.add_path("info.txt")
        lookback, length = lcs.get_lcs("main.py")
        assert lookback == 0
        assert length == 0

    def test_all_below_min_length(self):
        """All candidates have LCS < min_length -> no match."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("aaaaa.py")
        lcs.add_path("bbbbb.py")
        # LCS of "xxxxx.py" with stored paths = 3 (".py")
        lookback, length = lcs.get_lcs("xxxxx.py", min_length=5)
        assert lookback == 0
        assert length == 0


# ---------------------------------------------------------------------------
# Tests for get_lcs() — exact match / short-circuit
# ---------------------------------------------------------------------------


class TestGetLcsExactMatch:
    """When LCS equals the full query length, return immediately."""

    def test_exact_match_short_circuit(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("foo/bar.py")    # idx 0
        lcs.add_path("other.py")      # idx 1
        lookback, length = lcs.get_lcs("foo/bar.py")
        assert lookback == 2          # current_index=2, matched idx 0
        assert length == len("foo/bar.py")

    def test_exact_match_fresh_path(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("abc_def.py")    # idx 0
        lcs.add_path("xyz_def.py")    # idx 1
        lookback, length = lcs.get_lcs("xyz_def.py")
        assert lookback == 1          # current_index=2, matched idx 1
        assert length == len("xyz_def.py")

    def test_exact_duplicate_paths(self):
        """Same path added twice — picks the most recent full-length match
        (smallest lookback) via tie-breaking, mirroring V1/V2 behavior."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("common.py")     # idx 0
        lcs.add_path("other.py")      # idx 1
        lcs.add_path("common.py")     # idx 2
        lookback, length = lcs.get_lcs("common.py")
        # idx 0: LCS=9=path_length -> best_index=0, best_length=9
        # idx 1: LCS=3 -> skip
        # idx 2: LCS=9, tie, prev_index(2) > best_index(0) -> best_index=2
        # lookback = 3-2 = 1
        assert lookback == 1
        assert length == len("common.py")

    def test_identical_to_first_added(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("first.py")      # idx 0
        lcs.add_path("second.py")     # idx 1
        lookback, length = lcs.get_lcs("first.py")
        # Full match with idx 0 -> short circuit
        assert lookback == 2          # current_index=2, matched idx 0
        assert length == len("first.py")

    def test_identical_to_second_added(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("first.py")      # idx 0
        lcs.add_path("second.py")     # idx 1
        lookback, length = lcs.get_lcs("second.py")
        # Iterates: first.py(0) LCS="st.py"=5, second.py(1) full match -> short circuit
        assert lookback == 1          # current_index=2, matched idx 1
        assert length == len("second.py")

    def test_no_extension_exact_match(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("Makefile")
        lookback, length = lcs.get_lcs("Makefile")
        assert lookback == 1
        assert length == len("Makefile")


# ---------------------------------------------------------------------------
# Tests for get_lcs() — best match across all stored paths
# ---------------------------------------------------------------------------


class TestGetLcsBestMatch:
    """V3 scans all paths linearly and picks the longest LCS."""

    def test_best_match_among_multiple(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("aaaaa.py")      # idx 0
        lcs.add_path("bbaaa.py")      # idx 1
        lcs.add_path("cccc.py")       # idx 2
        lookback, length = lcs.get_lcs("xxaaa.py")
        # LCS with aaaaa.py(0): "aaa.py" = 6 -> best_index=0, best_length=6
        # LCS with bbaaa.py(1): "aaa.py" = 6, tie, prev_index(1) > best_index(0) -> best_index=1
        # LCS with ccccc.py(2): ".py" = 3
        # best_index=1, best_length=6 -> lookback=3-1=2
        assert lookback == 2
        assert length == 6

    def test_prefers_longer_lcs_over_closer_index(self):
        """A path with longer LCS wins even if its lookback distance is larger."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("short.py")          # idx 0, LCS=3 with query
        lcs.add_path("x_long_common_suffix.py")  # idx 1, LCS=17 with query
        lookback, length = lcs.get_lcs("query_common_suffix.py")
        # short.py(0): LCS=".py"=3
        # x_long_common_suffix.py(1): LCS="_common_suffix.py"=17
        assert lookback == 1
        assert length == len("_common_suffix.py")

    def test_tie_prefers_smaller_lookback(self):
        """Equal LCS lengths — the more recent path (smaller lookback) wins."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("aaa_x.py")      # idx 0
        lcs.add_path("bbb_x.py")      # idx 1
        lookback, length = lcs.get_lcs("ccc_x.py")
        # LCS("ccc_x.py", "aaa_x.py") = 5 -> best_index=0, best_length=5
        # LCS("ccc_x.py", "bbb_x.py") = 5, tie, prev_index(1) > best_index(0) -> best_index=1
        # best_index=1, lookback = 2-1 = 1
        assert lookback == 1
        assert length == 5

    def test_tie_three_candidates(self):
        """Three equal-LCS candidates — the most recent wins."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("a_common.py")   # idx 0
        lcs.add_path("b_common.py")   # idx 1
        lcs.add_path("c_common.py")   # idx 2
        lookback, length = lcs.get_lcs("x_common.py")
        # All share suffix "_common.py" = 10 chars with query
        # idx 0: LCS=10 -> best_index=0, best_length=10
        # idx 1: LCS=10, tie, prev_index(1) > 0 -> best_index=1
        # idx 2: LCS=10, tie, prev_index(2) > 1 -> best_index=2
        # lookback = 3-2 = 1
        assert lookback == 1
        assert length == 10

    def test_tie_full_length_via_suffix(self):
        """Multiple paths ending with the full query string — most recent wins."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("prefix_common.py")     # idx 0
        lcs.add_path("other.py")             # idx 1
        lcs.add_path("another_common.py")    # idx 2
        # Query is "common.py" = 9 chars. Both idx 0 and idx 2 end with "common.py"
        # but LCS("common.py", "prefix_common.py") = "common.py" = 9 = path_length
        # and LCS("common.py", "another_common.py") = "common.py" = 9 = path_length
        lookback, length = lcs.get_lcs("common.py")
        # idx 0: LCS=9=path_length -> best_index=0, best_length=9
        # idx 1: LCS=3 (".py") < 9 -> skip
        # idx 2: LCS=9, tie, prev_index(2) > 0 -> best_index=2
        # lookback = 3-2 = 1
        assert lookback == 1
        assert length == len("common.py")

    def test_cross_suffix_match(self):
        """V3 scans *all* paths, so paths with different extensions are compared."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("prefix_data.bin")   # idx 0
        lcs.add_path("data.txt")          # idx 1
        lookback, length = lcs.get_lcs("suffix_data.json")
        # LCS("suffix_data.json", "prefix_data.bin") = "data.bin"?? No:
        # "suffix_data.json" vs "prefix_data.bin":
        #   reversed: n-i-b-.-a-t-a-d-_... wait
        #   Actually: "suffix_data.json"[::-1] = "nosid.atad_xiffus"
        #   "prefix_data.bin"[::-1] = "nib.atad_xiferp"
        #   common reversed: "atad" -> 4
        # Actually let me trace more carefully:
        # "suffix_data.json" reversed: "nosid.atad_xiffus"
        # "prefix_data.bin" reversed: "nib.atad_xiferp"
        # Common suffix of reversed = "atad" = 4 chars
        # Wait no, LCS is longest common suffix *of the original strings*
        # suffix_data.json vs prefix_data.bin:
        # Last chars: n vs n -> match, next: o vs o -> no
        # Wait: "...json" vs "...bin": n vs n (1), o vs i (0)
        # Common suffix = "n" = 1
        #
        # "suffix_data.json" vs "data.txt":
        # "...json" vs ".txt": n vs t -> 0
        # Hmm, so LCS might be "a" or something?
        #
        # Actually let me think again:
        # "suffix_data.json" and "prefix_data.bin":
        # reversed string comparison:
        # "n" vs "n" -> match (idx 0)
        # "o" vs "i" -> no match
        # So LCS = "n" = 1
        #
        # "suffix_data.json" and "data.txt":
        # "n" vs "t" -> no match
        # So LCS = 0?
        #
        # Hmm wait, maybe there's something I'm missing.
        # Actually the strings are:
        #   s1 = "suffix_data.json"
        #   s2 = "prefix_data.bin"
        #
        # Last chars: s1[-1] = 'n', s2[-1] = 'n' -> match
        # s1[-2] = 'o', s2[-2] = 'i' -> no match
        # So LCS = 1
        #
        # s1 = "suffix_data.json"
        # s2 = "data.txt"
        # s1[-1] = 'n', s2[-1] = 't' -> no match
        # LCS = 0
        #
        # So best is idx 0 (prefix_data.bin) with LCS=1
        assert lookback == 2
        assert length == 1

    def test_best_cross_suffix_larger(self):
        """Larger cross-suffix LCS is preferred over smaller same-suffix LCS."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("aaaa.txt")          # idx 0, LCS with query = 1 ('.' only)
        lcs.add_path("bbbb_json_common")  # idx 1, LCS with query = 6 ("common")
        lookback, length = lcs.get_lcs("xxxx_json_common")
        # LCS("xxxx_json_common", "aaaa.txt"):
        #   "n" vs "t" -> no match at last char, LCS=0
        # LCS("xxxx_json_common", "bbbb_json_common"):
        #   matches exactly: "json_common" -> wait
        #   Actually "xxxx_json_common" vs "bbbb_json_common":
        #   Last chars: n vs n, o vs o, m vs m, m vs m, o vs o, c vs c,
        #   _ vs _, n vs n, o vs o, s vs s, j vs j -> match!
        #   Then _ vs b? No: "_" vs "b" -> no match
        #   Wait: "xxxx_json_common" and "bbbb_json_common":
        #   reversed:
        #   "nonmoc_nsij_xxxx" vs "nonmoc_nsij_bbbb"
        #   n,o,n,m,o,c,_,n,o,i,s,j,_ -> 12 matches then x vs b
        #   Hmm wait let me count more carefully
        #   "xxxx_json_common" = 17 chars
        #   "bbbb_json_common" = 17 chars
        #   reversed: "nonmoc_nsij_xxxx" "nonmoc_nsij_bbbb"
        #   Position 0-11: "nonmoc_nsij_"  (12 chars)
        #   Position 12: x vs b -> no match
        #   So LCS = 12
        #
        # Best = idx 1 with LCS=12
        lookback, length = lcs.get_lcs("xxxx_json_common")
        assert lookback == 1
        assert length == 12


# ---------------------------------------------------------------------------
# Tests for get_lcs() — min_length / max_length filters
# ---------------------------------------------------------------------------


class TestGetLcsMinMaxLength:
    """Filtering via min_length and max_length."""

    def test_min_length_excludes_shorter(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("aaaaa.py")
        lcs.add_path("bbbbb.py")
        # LCS of "xxxxx.py" with stored paths = 3 (".py")
        lookback, length = lcs.get_lcs("xxxxx.py", min_length=5)
        assert lookback == 0
        assert length == 0

    def test_min_length_allows_equal(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("aaaaa.py")
        lookback, length = lcs.get_lcs("bbbbb.py", min_length=3)
        # LCS(".py", ".py") = 3 >= min_length=3
        assert lookback == 1
        assert length == 3

    def test_min_length_allows_longer(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("prefix_suffix.py")
        lookback, length = lcs.get_lcs("other_suffix.py", min_length=5)
        # LCS = "_suffix.py" = 10 >= 5
        assert lookback == 1
        assert length >= 5

    def test_max_length_excludes_longer(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("aaaaa.py")
        lookback, length = lcs.get_lcs("bbbbb.py", max_length=2)
        # LCS(".py", ".py") = 3 > max_length=2
        assert lookback == 0
        assert length == 0

    def test_max_length_allows_equal(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("aaaaa.py")
        lookback, length = lcs.get_lcs("bbbbb.py", max_length=3)
        # LCS(".py", ".py") = 3 == max_length=3
        assert lookback == 1
        assert length == 3

    def test_max_length_filters_intermediate(self):
        """When best candidate exceeds max_length, the next best is used."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("abc_common.py")     # idx 0, LCS="common.py"=10 with query
        lcs.add_path("other.py")          # idx 1, LCS=".py"=3 with query
        lookback, length = lcs.get_lcs("xyz_common.py", max_length=5)
        # abc_common.py(0): LCS=10 > max_length=5, filtered
        # other.py(1): LCS=3 <= 5, accepted
        assert lookback == 1
        assert length == 3

    def test_min_and_max_combined(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("aaaaa.py")
        lcs.add_path("bbbbb.py")
        lcs.add_path("ccccc.py")
        lookback, length = lcs.get_lcs("xxxxx.py", min_length=3, max_length=4)
        # All stored paths have LCS=3 (".py"), ties resolved to smallest lookback
        # aaaaa.py(0): LCS=3 -> best_index=0, best_length=3
        # bbbbb.py(1): LCS=3, tie, prev_index(1) > best_index(0) -> best_index=1
        # ccccc.py(2): LCS=3, tie, prev_index(2) > best_index(1) -> best_index=2
        # best_index=2, lookback = 3-2 = 1
        assert lookback == 1
        assert length == 3

    def test_all_filters_exclude_everything(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("aaaaa.py")
        lcs.add_path("bbbbb.py")
        lookback, length = lcs.get_lcs("xxxxx.py", min_length=10)
        assert lookback == 0
        assert length == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary and pathological inputs."""

    def test_empty_string_path_stored(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("")                  # idx 0
        lookback, length = lcs.get_lcs("")
        # LCS("", "") = 0 < min_length=1
        assert lookback == 0
        assert length == 0

    def test_empty_string_path_queried(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("file.py")
        lookback, length = lcs.get_lcs("")
        assert lookback == 0
        assert length == 0

    def test_no_extension_query_with_extension(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("README")
        lookback, length = lcs.get_lcs("README.md")
        # LCS("README.md", "README"):
        #   "README.md" reversed = "dm.EMADER"
        #   "README" reversed = "EMADER"
        #   'd' != 'E' -> break immediately, LCS=0
        # No common suffix at all -> (0, 0)
        assert lookback == 0
        assert length == 0

    def test_path_with_only_extension(self):
        """A path that is just a file extension like .gitignore."""
        lcs = PathLookbackLCSV3()
        lcs.add_path(".gitignore")
        lookback, length = lcs.get_lcs(".gitignore")
        assert lookback == 1
        assert length == len(".gitignore")

    def test_path_with_trailing_dot(self):
        """A path like 'file.' should not crash."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("file.")
        lookback, length = lcs.get_lcs("file.")
        assert lookback == 1
        assert length == len("file.")

    def test_unicode_paths(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("数据/文件.py")
        lcs.add_path("备份/文件.py")
        lookback, length = lcs.get_lcs("新建/文件.py")
        # Both share "/文件.py" = 6 chars
        # idx 0: LCS=6 -> best_index=0, best_length=6
        # idx 1: LCS=6, tie, prev_index(1) > best_index(0) -> best_index=1
        # lookback = 2-1 = 1
        assert lookback == 1
        assert length == 6

    def test_single_char_stem(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("a.py")              # idx 0
        lcs.add_path("b.py")              # idx 1
        lookback, length = lcs.get_lcs("c.py")
        # LCS("c.py", "a.py") = 3 -> best_index=0, best_length=3
        # LCS("c.py", "b.py") = 3, tie, prev_index(1) > best_index(0) -> best_index=1
        # lookback = 2-1 = 1
        assert lookback == 1
        assert length == 3

    def test_very_long_paths(self):
        """Long paths should not cause issues."""
        long_a = "a" * 1000 + ".py"
        long_b = "b" * 1000 + ".py"
        lcs = PathLookbackLCSV3()
        lcs.add_path(long_a)
        lcs.add_path(long_b)
        lookback, length = lcs.get_lcs("x" * 1000 + ".py")
        # LCS = ".py" = 3
        # idx 0: LCS=3 -> best_index=0
        # idx 1: LCS=3, tie -> best_index=1 (smaller lookback)
        # lookback = 2-1 = 1
        assert lookback == 1
        assert length == 3

    def test_long_path_exact_match(self):
        long_path = "a" * 1000 + ".py"
        lcs = PathLookbackLCSV3()
        lcs.add_path(long_path)
        lookback, length = lcs.get_lcs(long_path)
        assert lookback == 1
        assert length == len(long_path)

    def test_path_with_directory_prefix(self):
        """Paths with same filename but different directories."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("/root/alpha/file.py")   # idx 0
        lcs.add_path("/root/beta/file.py")    # idx 1
        lookback, length = lcs.get_lcs("/root/gamma/file.py")
        # Both have LCS=9 ("a/file.py") with query
        # idx 0: LCS=9 -> best_index=0, best_length=9
        # idx 1: LCS=9, tie, prev_index(1) > best_index(0) -> best_index=1
        # lookback = 2-1 = 1
        assert lookback == 1
        assert length == 9

    def test_no_common_suffix_at_all(self):
        """Totally unrelated strings -> no match."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("abc")
        lookback, length = lcs.get_lcs("xyz")
        assert lookback == 0
        assert length == 0

    def test_partial_common_suffix(self):
        """Partially overlapping suffix."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("prefix_data_core")
        lcs.add_path("other_data")
        lookback, length = lcs.get_lcs("new_data_core")
        # LCS with prefix_data_core(0): "_data_core" = 10
        #   Actually: "new_data_core" vs "prefix_data_core":
        #   "eroc_atad_wen" vs "eroc_atad_xiferp"
        #   e==e,r==r,o==o,c==c,_,==_,a==a,t==t,a==a,d==d -> 10 matches
        #   then '_' vs 'e' -> no
        #   So LCS = 10
        # LCS with other_data(1): "new_data_core" vs "other_data":
        #   "eroc_atad_wen" vs "atad_rehto"
        #   e==e -> wait: e vs a -> no match, LCS=0
        # Actually let me retrace:
        # "new_data_core" reversed = "eroc_atad_wen"
        # "other_data" reversed = "atad_rehto"
        # e vs a -> no match. LCS=0
        # So best is idx 0 with LCS=10
        assert lookback == 2
        assert length == 10


# ---------------------------------------------------------------------------
# Regression: verify V3 scans all paths (no bucketing)
# ---------------------------------------------------------------------------


class TestNoBucketing:
    """V3 does NOT use bucketing — all paths are compared regardless of suffix,
    last char, or any derived key."""

    def test_scan_all_does_not_favor_same_suffix(self):
        """A cross-suffix match with longer LCS wins over a same-suffix match
        with shorter LCS — V3 scans everything."""
        lcs = PathLookbackLCSV3()
        lcs.add_path("file_a.txt")          # idx 0
        lcs.add_path("x_common_suffix.py")  # idx 1
        lookback, length = lcs.get_lcs("y_common_suffix.py")
        # LCS with file_a.txt(0): reversed "txe.aelif" vs "yppus_nommoc_y"
        #   "y" vs "t" -> no, LCS=0
        # LCS with x_common_suffix.py(1): "_common_suffix.py" = 17
        assert lookback == 1
        assert length == 17

    def test_many_paths_no_crash(self):
        """Linear scan over many paths should work without blowing up."""
        lcs = PathLookbackLCSV3()
        for i in range(100):
            lcs.add_path(f"prefix_{i}_end.py")
        # All 100 paths share ".py" (3 chars) with query
        # Ties resolve to the most recent path (idx 99) for smallest lookback
        # lookback = 100-99 = 1
        lookback, length = lcs.get_lcs("query_other.py")
        assert lookback == 1
        assert length == 3

    def test_single_path(self):
        lcs = PathLookbackLCSV3()
        lcs.add_path("single.py")
        lookback, length = lcs.get_lcs("single.py")
        assert lookback == 1
        assert length == len("single.py")
