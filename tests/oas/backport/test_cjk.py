import pytest

from oas.backport.cjk import cjk_pad, cjk_width


class TestCjkWidth:
    """Tests for cjk_width with various character categories."""

    @pytest.mark.parametrize("text, expected", [
        # Pure ASCII (isascii=True, fast path)
        ("", 0),
        (" ", 1),
        ("hello", 5),
        ("abc123!@#", 9),
        # Accented Latin (non-ASCII but non-wide, isascii=False, wide=0)
        ("é", 1),
        ("ñ", 1),
        ("ü", 1),
        ("café", 4),
        ("São Paulo", 9),
        ("résumé", 6),
        # CJK Unified Ideographs (in \u4e00-\u9fff)
        ("你好", 4),
        ("世界", 4),
        ("你好世界", 8),
        # Korean Hangul (in \uac00-\ud7af)
        ("안녕", 4),
        ("한국어", 6),
        # Japanese hiragana (in \u3040-\u309f, within \u2e80-\u4dbf)
        ("こんにちは", 10),
        ("ありがとう", 10),
        # Japanese katakana (in \u30a0-\u30ff, within \u2e80-\u4dbf)
        ("コンニチハ", 10),
        # Fullwidth punctuation (in \uff01-\uff60)
        ("，", 2),  # U+FF0C fullwidth comma
        ("！", 2),  # U+FF01 fullwidth exclamation
        ("？", 2),  # U+FF1F fullwidth question
        ("（", 2),  # U+FF08 fullwidth left parenthesis
        ("）", 2),  # U+FF09 fullwidth right parenthesis
        ("～", 2),  # U+FF5E fullwidth tilde
        ("！！", 4),
        ("！？！", 6),
        # Japanese brackets (in \u2e80-\u4dbf)
        ("「", 2),  # U+300C left corner bracket
        ("」", 2),  # U+300D right corner bracket
        ("【", 2),  # U+3010 left black lenticular bracket
        ("】", 2),  # U+3011 right black lenticular bracket
        # CJK Compatibility (in \uf900-\ufaff)
        ("豈", 2),  # U+F900 CJK compatibility ideograph
        # Vertical Forms (in \ufe10-\ufe19)
        ("︐", 2),  # U+FE10 vertical comma
        # CJK Compatibility Forms (in \ufe30-\ufe6f)
        ("︰", 2),  # U+FE30 vertical two-dot leader
        # Fullwidth Signs (in \uffe0-\uffe6)
        ("￠", 2),  # U+FFE0 fullwidth cent sign
        ("￡", 2),  # U+FFE1 fullwidth pound sign
        # Emoji (in \U0001f300-\U0001ffff)
        ("🎉", 2),  # U+1F389 party popper
        ("🌟", 2),  # U+1F31F glowing star
        # Mixed content
        ("hello你好", 9),
        ("helloありがとう", 15),
        ("你好，世界", 10),
        ("abc你好 def", 11),
    ])
    def test_cjk_width(self, text, expected):
        assert cjk_width(text) == expected


class TestCjkPadChar:
    """Tests for cjk_pad with custom padding character."""

    @pytest.mark.parametrize("text, width, align, char, expected", [
        # Left padding with custom char
        ("hello", 8, "left", "-", "hello---"),
        ("你好", 6, "left", ".", "你好.."),
        # Right padding with custom char
        ("hello", 8, "right", "-", "---hello"),
        ("你好", 6, "right", ".", "..你好"),
        # Center padding with custom char - even padding
        ("ab", 6, "center", "-", "--ab--"),
        ("ab", 6, "center", ".", "..ab.."),
        # Center padding with custom char - odd padding
        ("abc", 7, "center", "-", "--abc--"),
        # overflow - char has no effect
        ("longword", 3, "left", "-", "longword"),
        ("你好世界", 4, "left", ".", "你好世界"),
        # CJK with custom char, mixed content
        ("hello你好", 12, "center", "-", "-hello你好--"),
    ])
    def test_cjk_pad_char(self, text, width, align, char, expected):
        assert cjk_pad(text, width, align, char) == expected


class TestCjkPadLatin:
    """Tests for cjk_pad with non-fullwidth Latin characters (isascii=True or
    non-wide non-ASCII like accented chars such as é, ñ, ü)."""

    @pytest.mark.parametrize("text, width, align, expected", [
        # left alignment
        ("hello", 8, "left", "hello   "),
        ("a", 3, "left", "a  "),
        ("", 4, "left", "    "),
        ("!?", 4, "left", "!?  "),
        # right alignment
        ("hello", 8, "right", "   hello"),
        ("a", 3, "right", "  a"),
        ("", 4, "right", "    "),
        # center alignment - even padding
        ("ab", 6, "center", "  ab  "),
        ("a", 5, "center", "  a  "),
        # center alignment - odd padding (extra space on right)
        ("abc", 8, "center", "  abc   "),
        ("ab", 5, "center", " ab  "),
        # exact fit
        ("hello", 5, "left", "hello"),
        ("hello", 5, "right", "hello"),
        ("hello", 5, "center", "hello"),
        # overflow (target < len(text), ljust/rjust don't truncate)
        ("hello", 3, "left", "hello"),
        ("hello", 2, "right", "hello"),
        ("hello", 1, "center", "hello"),
        # numeric characters
        ("123", 6, "left", "123   "),
        ("42", 5, "center", " 42  "),
        # accented Latin characters (non-ASCII, non-wide, display width 1 per char)
        ("café", 8, "left", "café    "),
        ("café", 8, "right", "    café"),
        ("café", 8, "center", "  café  "),
        ("café", 3, "left", "café"),  # overflow
        ("São Paulo", 12, "left", "São Paulo   "),
        ("résumé", 10, "left", "résumé    "),
        ("résumé", 10, "right", "    résumé"),
        ("résumé", 10, "center", "  résumé  "),
    ])
    def test_cjk_pad(self, text, width, align, expected):
        assert cjk_pad(text, width, align) == expected


class TestCjkPadCjk:
    """Tests for cjk_pad with CJK, Hangul, and Japanese characters (中日韩字符)."""

    @pytest.mark.parametrize("text, width, align, expected", [
        # Chinese characters - left alignment
        ("你好", 6, "left", "你好  "),
        ("世界", 4, "left", "世界"),
        # Chinese characters - right alignment
        ("你好", 6, "right", "  你好"),
        ("你好", 8, "right", "    你好"),
        # Chinese characters - center alignment (even and odd padding)
        ("你好", 6, "center", " 你好 "),
        ("你好", 7, "center", " 你好  "),
        ("你好", 8, "center", "  你好  "),
        # Korean Hangul (in \uac00-\ud7af)
        ("안녕", 6, "left", "안녕  "),
        # Multiple CJK characters - overflow
        ("你好世界", 6, "left", "你好世界"),
        ("你好世界", 4, "center", "你好世界"),
        # Mixed CJK and ASCII
        ("hello你好", 12, "left", "hello你好   "),
        ("hello你好", 12, "right", "   hello你好"),
        ("hello你好", 12, "center", " hello你好  "),
        # Japanese hiragana (in \u3040-\u309f, within \u2e80-\u4dbf)
        ("こんにちは", 12, "left", "こんにちは  "),
        ("こんにちは", 12, "right", "  こんにちは"),
        ("こんにちは", 12, "center", " こんにちは "),
        ("ありがとう", 6, "left", "ありがとう"),  # overflow
        # Japanese katakana (in \u30a0-\u30ff, within \u2e80-\u4dbf)
        ("コンニチハ", 12, "left", "コンニチハ  "),
        # Japanese quotation marks（「」U+300c,U+300d, within \u2e80-\u4dbf）
        ("「こんにちは」", 16, "left", "「こんにちは」  "),
        ("「こんにちは」", 10, "left", "「こんにちは」"),  # overflow
        # Mixed CJK and Japanese
        ("你好こんにちは", 16, "left", "你好こんにちは  "),
        # Mixed ASCII and Japanese
        ("helloありがとう", 16, "left", "helloありがとう "),
        # Mixed kanji and kana
        ("日本語テスト", 14, "left", "日本語テスト  "),
    ])
    def test_cjk_pad(self, text, width, align, expected):
        assert cjk_pad(text, width, align) == expected


class TestCjkPadFullwidthPunctuation:
    """Tests for cjk_pad with fullwidth punctuation (全角标点符号)."""

    @pytest.mark.parametrize("text, width, align, expected", [
        # Fullwidth comma（，U+FF0C）and full stop（。U+3002）
        ("，", 4, "left", "，  "),
        ("。", 4, "left", "。  "),
        ("、", 4, "left", "、  "),
        # Fullwidth exclamation（！U+FF01）and question（？U+FF1F）
        ("！", 4, "right", "  ！"),
        ("？", 4, "right", "  ？"),
        # Fullwidth brackets（【】U+3010,U+3011 and （）U+FF08,U+FF09）
        ("【", 4, "center", " 【 "),
        ("】", 4, "center", " 】 "),
        ("（", 4, "center", " （ "),
        ("）", 4, "center", " ） "),
        # Fullwidth tilde（～U+FF5E）
        ("～", 4, "left", "～  "),
        # Multiple fullwidth punctuation marks - padded
        ("！！", 6, "left", "！！  "),
        ("！？！", 8, "center", " ！？！ "),
        # Mixed fullwidth punctuation and CJK
        ("你好，世界", 12, "left", "你好，世界  "),
        # Overflow
        ("，，，，", 4, "left", "，，，，"),
    ])
    def test_cjk_pad(self, text, width, align, expected):
        assert cjk_pad(text, width, align) == expected