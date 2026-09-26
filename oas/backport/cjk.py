import re
from typing import Literal

from oas.backport import str_center

# Regex matching CJK characters, fullwidth punctuation, emoji, and other
# characters that occupy 2 display columns in a monospace terminal.
_RE_WIDE = re.compile(
    r'['
    r'\u2e80-\u4dbf'  # CJK Radicals, Kangxi, CJK Ext A
    r'\u4e00-\u9fff'  # CJK Unified Ideographs
    r'\uac00-\ud7af'  # Hangul Syllables
    r'\uf900-\ufaff'  # CJK Compatibility
    r'\ufe10-\ufe19'  # Vertical Forms
    r'\ufe30-\ufe6f'  # CJK Compatibility Forms
    r'\uff01-\uff60'  # Fullwidth Forms
    r'\uffe0-\uffe6'  # Fullwidth Signs
    r'\U0001f300-\U0001ffff'  # Emoji, CJK Ext B+
    r']'
)
T_ALIGN = Literal['left', 'center', 'right']


def cjk_width(text):
    """
    Approximate display width of *text*.

    Non-ASCII characters matched by ``_RE_WIDE`` count as 2 display columns;
    all other characters count as 1.  Pure ASCII strings skip the regex
    entirely for performance.

    Args:
        text (str): Input string.

    Returns:
        int: Display width.
    """
    if text.isascii():
        return len(text)
    return len(text) + len(_RE_WIDE.findall(text))


def cjk_pad(text, width, align: T_ALIGN = 'left', char=' '):
    """
    Pad *text* to display *width*, accounting for CJK double-width chars.

    Args:
        text (str): String to pad.
        width (int): Target display width.
        align: ``'left'``, ``'right'``, or ``'center'``.
            Defaults to ``'left'``.
        char (str): Padding character. Defaults to space.

    Returns:
        str: Padded string.
    """
    if text.isascii():
        target = width
    else:
        wide = len(_RE_WIDE.findall(text))
        target = width - wide
        if len(text) >= target:
            return text

    if align == 'left':
        return text.ljust(target, char)
    if align == 'right':
        return text.rjust(target, char)
    if align == 'center':
        return str_center(text, target, char)
    return text.ljust(target, char)
