import pytest

from oas.ext.algorithm.lcp import get_lcp, get_lcs


class TestGetLcpStr:
    """Tests for get_lcp with str inputs."""

    @pytest.mark.parametrize("s1, s2, expected", [
        ("abc", "abd", "ab"),
        ("hello", "helicopter", "hel"),
        ("prefix", "prefix", "prefix"),
        ("abc", "xyz", ""),
        ("", "abc", ""),
        ("abc", "", ""),
        ("", "", ""),
        ("a", "a", "a"),
        ("a", "b", ""),
        ("case", "CASE", ""),
        ("hello world", "hello there", "hello "),
        # Unicode tests
        ("café", "café au lait", "café"),
        ("你好世界", "你好", "你好"),
        ("你好世界", "你好吗", "你好"),
        # Very long strings
        ("a" * 1000 + "b", "a" * 1000 + "c", "a" * 1000),
    ])
    def test_str_lcp(self, s1, s2, expected):
        """get_lcp with str inputs should return str."""
        result = get_lcp(s1, s2)
        assert result == expected
        assert isinstance(result, str)

    def test_returns_shorter_when_one_is_prefix(self):
        """When one string is a prefix of the other, the shorter is returned."""
        assert get_lcp("ab", "abc") == "ab"
        assert get_lcp("abc", "ab") == "ab"


class TestGetLcpBytes:
    """Tests for get_lcp with bytes inputs."""

    @pytest.mark.parametrize("s1, s2, expected", [
        (b"abc", b"abd", b"ab"),
        (b"hello", b"helicopter", b"hel"),
        (b"prefix", b"prefix", b"prefix"),
        (b"abc", b"xyz", b""),
        (b"", b"abc", b""),
        (b"abc", b"", b""),
        (b"", b"", b""),
        (b"a", b"a", b"a"),
        (b"a", b"b", b""),
        (b"hello world", b"hello there", b"hello "),
        # Binary data including null bytes
        (b"\x00\x01\x02", b"\x00\x01\x03", b"\x00\x01"),
        (b"\xff\xfe", b"\xff\xff", b"\xff"),
        # Very long bytes
        (b"a" * 1000 + b"b", b"a" * 1000 + b"c", b"a" * 1000),
    ])
    def test_bytes_lcp(self, s1, s2, expected):
        """get_lcp with bytes inputs should return bytes."""
        result = get_lcp(s1, s2)
        assert result == expected
        assert isinstance(result, bytes)

    def test_returns_shorter_when_one_is_prefix(self):
        """When one bytes is a prefix of the other, the shorter is returned."""
        assert get_lcp(b"ab", b"abc") == b"ab"
        assert get_lcp(b"abc", b"ab") == b"ab"


class TestGetLcpEdgeCases:
    """Edge case and regression tests for get_lcp."""

    def test_empty_inputs(self):
        """Both empty str and bytes should return empty of the same type."""
        assert get_lcp("", "") == ""
        assert isinstance(get_lcp("", ""), str)
        assert get_lcp(b"", b"") == b""
        assert isinstance(get_lcp(b"", b""), bytes)

    def test_single_char_match(self):
        """Single character match for both str and bytes."""
        assert get_lcp("x", "x") == "x"
        assert isinstance(get_lcp("x", "x"), str)
        assert get_lcp(b"x", b"x") == b"x"
        assert isinstance(get_lcp(b"x", b"x"), bytes)

    def test_no_common_prefix(self):
        """When there is no common prefix, empty string/bytes of correct type is returned."""
        result = get_lcp("abc", "xyz")
        assert result == ""
        assert isinstance(result, str)

        result = get_lcp(b"abc", b"xyz")
        assert result == b""
        assert isinstance(result, bytes)

    def test_identical_long_inputs(self):
        """Identical long inputs should return the full string/bytes."""
        long_str = "hello" * 200
        assert get_lcp(long_str, long_str) == long_str
        assert isinstance(get_lcp(long_str, long_str), str)

        long_bytes = b"hello" * 200
        assert get_lcp(long_bytes, long_bytes) == long_bytes
        assert isinstance(get_lcp(long_bytes, long_bytes), bytes)


class TestGetLcsStr:
    """Tests for get_lcs with str inputs."""

    @pytest.mark.parametrize("s1, s2, expected", [
        ("abc", "dbc", "bc"),
        ("hello", "jello", "ello"),
        ("suffix", "suffix", "suffix"),
        ("abc", "xyz", ""),
        ("", "abc", ""),
        ("abc", "", ""),
        ("", "", ""),
        ("a", "a", "a"),
        ("a", "b", ""),
        ("case", "baSE", ""),
        ("hello world", "goodbye world", " world"),
        # Unicode tests
        ("café", "café au lait", ""),
        ("世界你好", "你好", "你好"),
        ("世界你好", "吗你好", "你好"),
        # Very long strings
        ("b" + "a" * 1000, "c" + "a" * 1000, "a" * 1000),
    ])
    def test_str_lcs(self, s1, s2, expected):
        """get_lcs with str inputs should return str."""
        result = get_lcs(s1, s2)
        assert result == expected
        assert isinstance(result, str)

    def test_returns_shorter_when_one_is_suffix(self):
        """When one string is a suffix of the other, the shorter is returned."""
        assert get_lcs("bc", "abc") == "bc"
        assert get_lcs("abc", "bc") == "bc"


class TestGetLcsBytes:
    """Tests for get_lcs with bytes inputs."""

    @pytest.mark.parametrize("s1, s2, expected", [
        (b"abc", b"dbc", b"bc"),
        (b"hello", b"jello", b"ello"),
        (b"suffix", b"suffix", b"suffix"),
        (b"abc", b"xyz", b""),
        (b"", b"abc", b""),
        (b"abc", b"", b""),
        (b"", b"", b""),
        (b"a", b"a", b"a"),
        (b"a", b"b", b""),
        (b"hello world", b"goodbye world", b" world"),
        # Binary data including null bytes
        (b"\x02\x00\x01", b"\x03\x00\x01", b"\x00\x01"),
        (b"\xfe\xff", b"\xff\xff", b"\xff"),
        # Very long bytes
        (b"b" + b"a" * 1000, b"c" + b"a" * 1000, b"a" * 1000),
    ])
    def test_bytes_lcs(self, s1, s2, expected):
        """get_lcs with bytes inputs should return bytes."""
        result = get_lcs(s1, s2)
        assert result == expected
        assert isinstance(result, bytes)

    def test_returns_shorter_when_one_is_suffix(self):
        """When one bytes is a suffix of the other, the shorter is returned."""
        assert get_lcs(b"bc", b"abc") == b"bc"
        assert get_lcs(b"abc", b"bc") == b"bc"


class TestGetLcsEdgeCases:
    """Edge case and regression tests for get_lcs."""

    def test_empty_inputs(self):
        """Both empty str and bytes should return empty of the same type."""
        assert get_lcs("", "") == ""
        assert isinstance(get_lcs("", ""), str)
        assert get_lcs(b"", b"") == b""
        assert isinstance(get_lcs(b"", b""), bytes)

    def test_single_char_match(self):
        """Single character match for both str and bytes."""
        assert get_lcs("x", "x") == "x"
        assert isinstance(get_lcs("x", "x"), str)
        assert get_lcs(b"x", b"x") == b"x"
        assert isinstance(get_lcs(b"x", b"x"), bytes)

    def test_no_common_suffix(self):
        """When there is no common suffix, empty string/bytes of correct type is returned."""
        result = get_lcs("abc", "xyz")
        assert result == ""
        assert isinstance(result, str)

        result = get_lcs(b"abc", b"xyz")
        assert result == b""
        assert isinstance(result, bytes)

    def test_identical_long_inputs(self):
        """Identical long inputs should return the full string/bytes."""
        long_str = "hello" * 200
        assert get_lcs(long_str, long_str) == long_str
        assert isinstance(get_lcs(long_str, long_str), str)

        long_bytes = b"hello" * 200
        assert get_lcs(long_bytes, long_bytes) == long_bytes
        assert isinstance(get_lcs(long_bytes, long_bytes), bytes)

    def test_suffix_overlap(self):
        """Suffix that overlaps partially in the shorter string."""
        assert get_lcs("xyzabc", "abc") == "abc"
        assert get_lcs("abc", "xyzabc") == "abc"
