import pytest

from script.misc.filter import parse_filter, remove_hash_comment

# -----------------------------------------------------------------------------
# Tests for remove_hash_comment
# -----------------------------------------------------------------------------


def test_remove_hash_comment_basic():
    """Test simple string without comments."""
    s = "DailyEvent\nGem-8"
    expected = "DailyEvent\nGem-8"
    assert remove_hash_comment(s) == expected


def test_remove_hash_comment_inline():
    """Test removal of inline comments."""
    s = "Gem-8 # This is a gem"
    expected = "Gem-8"
    assert remove_hash_comment(s) == expected


def test_remove_hash_comment_full_line():
    """Test removal of lines that are entirely comments."""
    s = """
    DailyEvent
    # This entire line should go
    Gem-8
    """
    expected = "DailyEvent\nGem-8"
    assert remove_hash_comment(s) == expected


def test_remove_hash_comment_whitespace_handling():
    """Test that surrounding whitespace is stripped and empty lines are removed."""
    # Trailing spaces after "Gem-8" are intentional test data
    s = '\n\n      DailyEvent   # Comment\n\n    Gem-8  \n'
    expected = "DailyEvent\nGem-8"
    assert remove_hash_comment(s) == expected


def test_remove_hash_comment_empty_result():
    """Test that a string of only comments/whitespace returns an empty string."""
    s = """
    # comment 1
      # comment 2
    """
    assert remove_hash_comment(s) == ""


# -----------------------------------------------------------------------------
# Tests for parse_filter
# -----------------------------------------------------------------------------

def test_parse_filter_simple_chain():
    """Test a standard DSL chain."""
    s = "DailyEvent > Gem-8 > Gem-4"
    expected = ["DailyEvent", "Gem-8", "Gem-4"]
    assert parse_filter(s) == expected


def test_parse_filter_removes_internal_whitespace():
    """
    The code does re.sub('\s', '', s).
    Verify that spaces *inside* items are removed (e.g., 'Gem - 8' -> 'Gem-8').
    """
    s = "Daily Event > Gem - 8"
    expected = ["DailyEvent", "Gem-8"]
    assert parse_filter(s) == expected


def test_parse_filter_docstring_example():
    """Test the complex example provided in the docstring."""
    s = '''
        DailyEvent > Gem-8 > Gem-4 > Gem-2 > ExtraCube-0:30 # this is an inline comment
        > UrgentCube-1:30 > UrgentCube-1:45 > UrgentCube-3
        # this is a comment
        > UrgentCube-2:15 > UrgentCube-4 > UrgentCube-6
    '''
    result = parse_filter(s)

    # Verify specific sequence integrity
    assert result[0] == "DailyEvent"
    assert result[4] == "ExtraCube-0:30"
    assert "UrgentCube-1:30" in result
    assert "UrgentCube-6" in result
    assert len(result) == 11  # Count of items in the example


@pytest.mark.parametrize("unicode_char", [
    '＞',  # \uFF1E
    '﹥',  # \uFE65
    '›',  # \u203a
    '˃',  # \u02c3
    'ᐳ',  # \u1433
    '❯',  # \u276F
])
def test_parse_filter_unicode_replacements(unicode_char):
    """Test that various unicode arrows are normalized to standard '>'."""
    s = f"ItemA {unicode_char} ItemB"
    expected = ["ItemA", "ItemB"]
    assert parse_filter(s) == expected


def test_parse_filter_mixed_separators():
    """Test mixing standard arrows and unicode arrows."""
    s = "A > B ＞ C ❯ D"
    expected = ["A", "B", "C", "D"]
    assert parse_filter(s) == expected


def test_parse_filter_empty_items():
    """Test that leading/trailing/duplicate separators do not create empty items."""
    # The code uses `if i` to filter out empty splits
    s = "> A > > B >"
    expected = ["A", "B"]
    assert parse_filter(s) == expected


def test_parse_filter_input_types():
    """
    The code runs str(s) at the start.
    Test to ensure it handles non-string input gracefully if passed.
    """
    # Just to ensure it doesn't crash, though typical usage is string
    s = 123
    # "123" -> splits to ["123"]
    assert parse_filter(s) == ["123"]


def test_parse_filter_none():
    """Test behavior when None is passed (str(None) -> 'None')."""
    # This is an edge case of str(None)
    assert parse_filter(None) == ["None"]
