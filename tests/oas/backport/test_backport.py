from typing import get_args, Literal

import msgspec
import pytest

from oas.backport import str_center


class TestRemovePrefix:
    # OAS 3.14: 直接用原生 str.removeprefix / bytes.removeprefix
    def test_removeprefix(self):
        # Normal case
        assert "prefix_text".removeprefix("prefix_") == "text"
        # No match
        assert "text".removeprefix("prefix_") == "text"
        # Empty prefix
        assert "prefix_text".removeprefix("") == "prefix_text"
        # Partial match at start
        assert "aaa".removeprefix("aa") == "a"
        # Prefix longer than string
        assert "aaa".removeprefix("aaaa") == "aaa"
        # Match but not at start
        assert "text_prefix".removeprefix("prefix") == "text_prefix"
        # Empty input string
        assert "".removeprefix("prefix") == ""
        assert "".removeprefix("") == ""

    def test_removeprefix_bytes(self):
        # Normal case
        assert b"prefix_text".removeprefix(b"prefix_") == b"text"
        # No match
        assert b"text".removeprefix(b"prefix_") == b"text"
        # Empty prefix
        assert b"prefix_text".removeprefix(b"") == b"prefix_text"
        # Partial match at start
        assert b"aaa".removeprefix(b"aa") == b"a"
        # Prefix longer than string
        assert b"aaa".removeprefix(b"aaaa") == b"aaa"
        # Match but not at start
        assert b"text_prefix".removeprefix(b"prefix") == b"text_prefix"
        # Empty input string
        assert b"".removeprefix(b"prefix") == b""
        assert b"".removeprefix(b"") == b""


class TestRemoveSuffix:
    # OAS 3.14: 直接用原生 str.removesuffix / bytes.removesuffix
    def test_removesuffix(self):
        # Normal case
        assert "text_suffix".removesuffix("_suffix") == "text"
        # No match
        assert "text".removesuffix("_suffix") == "text"
        # Empty suffix
        assert "text_suffix".removesuffix("") == "text_suffix"
        # Partial match at end
        assert "aaa".removesuffix("aa") == "a"
        # Suffix longer than string
        assert "aaa".removesuffix("aaaa") == "aaa"
        # Match but not at end
        assert "suffix_text".removesuffix("suffix") == "suffix_text"
        # Empty input string
        assert "".removesuffix("suffix") == ""
        assert "".removesuffix("") == ""

    def test_removesuffix_bytes(self):
        # Normal case
        assert b"text_suffix".removesuffix(b"_suffix") == b"text"
        # No match
        assert b"text".removesuffix(b"_suffix") == b"text"
        # Empty suffix
        assert b"text_suffix".removesuffix(b"") == b"text_suffix"
        # Partial match at end
        assert b"aaa".removesuffix(b"aa") == b"a"
        # Suffix longer than string
        assert b"aaa".removesuffix(b"aaaa") == b"aaa"
        # Match but not at end
        assert b"suffix_text".removesuffix(b"suffix") == b"suffix_text"
        # Empty input string
        assert b"".removesuffix(b"suffix") == b""
        assert b"".removesuffix(b"") == b""


class TestToLiteral:
    # OAS 3.14: 直接用原生 Literal[*items]（3.11+ 内置解包）
    def test_to_literal_content(self):
        """
        Test if the resulting Literal can be traversed for correct content
        """
        items = ["zh", "en", "ja", "kr"]
        lang_t = Literal[*items]
        # Use get_args to verify the content of the Literal type
        assert get_args(lang_t) == ("zh", "en", "ja", "kr")

    def test_to_literal_msgspec(self):
        """
        Test if the resulting Literal can be used as a msgspec struct field annotation
        """
        items = ["zh", "en"]
        lang_t = Literal[*items]

        class UserConfig(msgspec.Struct):
            lang: lang_t

        # Test valid input
        data_zh = msgspec.json.decode(b'{"lang": "zh"}', type=UserConfig)
        assert data_zh.lang == "zh"
        data_en = msgspec.json.decode(b'{"lang": "en"}', type=UserConfig)
        assert data_en.lang == "en"

        # Test invalid input
        with pytest.raises(msgspec.ValidationError):
            msgspec.json.decode(b'{"lang": "ja"}', type=UserConfig)

        with pytest.raises(msgspec.ValidationError):
            msgspec.json.decode(b'{"lang": 123}', type=UserConfig)


class TestProcessCpuCount:
    # OAS 3.14: 直接用原生 os.process_cpu_count()
    def test_process_cpu_count_call(self):
        """
        Ensure process_cpu_count runs without raising exceptions
        """
        import os

        count = os.process_cpu_count()
        assert count is None or isinstance(count, int)


class TestStrCenter:
    """Tests for str_center — extra char goes to right when padding is odd."""

    @pytest.mark.parametrize("text, width, char, expected", [
        # even padding — same as str.center()
        ("ab", 6, ' ', "  ab  "),
        ("a", 5, ' ', "  a  "),
        ("", 4, ' ', "    "),
        # odd padding — extra char on RIGHT
        ("ab", 5, ' ', " ab  "),
        ("abc", 7, ' ', "  abc  "),
        ("a", 4, ' ', " a  "),
        # width <= len(text) — return as-is
        ("hello", 3, ' ', "hello"),
        ("hello", 5, ' ', "hello"),
        # custom padding char
        ("ab", 6, '-', "--ab--"),
        ("ab", 5, '-', "-ab--"),
        ("a", 4, '.', ".a.."),
        ("a", 3, '.', ".a."),
    ])
    def test_str_center(self, text, width, char, expected):
        assert str_center(text, width, char) == expected