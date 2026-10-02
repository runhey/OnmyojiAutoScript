from datetime import datetime, timedelta, timezone

import pytest

from oas.ext.timez import fromisoformat

# A collection of test cases: (test_id, input_string, expected_datetime_object)
SUCCESS_CASES = [
    # --- 1. The key feature: 'Z' suffix handling ---
    (
        "zulu_no_ms",
        "2023-11-22T10:30:00Z",
        datetime(2023, 11, 22, 10, 30, 0, tzinfo=timezone.utc),
    ),
    (
        "zulu_with_ms",
        "2023-11-22T10:30:00.123456Z",
        datetime(2023, 11, 22, 10, 30, 0, 123456, tzinfo=timezone.utc),
    ),
    (
        "zulu_lowercase_z",
        "2023-11-22T10:30:00z",  # Test case-insensitivity
        datetime(2023, 11, 22, 10, 30, 0, tzinfo=timezone.utc),
    ),

    # --- 2. Regression tests: ensure standard formats still work ---
    (
        "utc_offset",
        "2023-11-22T10:30:00+00:00",
        datetime(2023, 11, 22, 10, 30, 0, tzinfo=timezone.utc),
    ),
    (
        "positive_offset",
        "2023-11-22T12:30:00+02:00",
        datetime(2023, 11, 22, 12, 30, 0, tzinfo=timezone(timedelta(hours=2))),
    ),
    (
        "negative_offset_ms",
        "2023-11-22T05:30:00.500-05:00",
        datetime(2023, 11, 22, 5, 30, 0, 500000, tzinfo=timezone(timedelta(hours=-5))),
    ),
    (
        "naive_time",
        "2023-11-22T18:30:00",
        datetime(2023, 11, 22, 18, 30, 0),
    ),
    (
        "date_only",
        "2023-11-22",
        datetime(2023, 11, 22, 0, 0, 0),
    ),

    # --- 3. Combination of 'Z' suffix and space separator ---
    (
        "space_sep_naive",
        "2023-11-22 18:30:00",
        datetime(2023, 11, 22, 18, 30, 0),
    ),
    (
        "space_sep_offset",
        "2023-11-22 12:30:00+02:00",
        datetime(2023, 11, 22, 12, 30, 0, tzinfo=timezone(timedelta(hours=2))),
    ),
    (
        "space_sep_zulu",
        "2023-11-22 10:30:00Z",
        datetime(2023, 11, 22, 10, 30, 0, tzinfo=timezone.utc),
    ),
    (
        "space_sep_zulu_ms",
        "2023-11-22 10:30:00.123456Z",
        datetime(2023, 11, 22, 10, 30, 0, 123456, tzinfo=timezone.utc),
    ),
]


@pytest.mark.parametrize(
    "test_id, input_string, expected",
    SUCCESS_CASES,
    ids=[case[0] for case in SUCCESS_CASES]
)
def test_fromisoformat_backport_success(test_id, input_string, expected):
    """
    Tests that the backport function correctly parses valid ISO strings,
    including those with the 'Z' suffix.
    """
    result = fromisoformat(input_string)
    assert result == expected
    # Also check timezone info explicitly
    assert result.tzinfo == expected.tzinfo


def test_invalid_format_raises_value_error():
    """
    Tests that the function properly raises ValueError for invalid strings,
    delegating the error from the built-in parser.
    """
    with pytest.raises(ValueError):
        fromisoformat("not-a-datetime")


def test_invalid_type_raises_type_error():
    """
    Tests that the function raises a TypeError for non-string inputs.
    """
    with pytest.raises(TypeError, match="must be str"):
        fromisoformat(12345)

    with pytest.raises(TypeError):
        fromisoformat(None)
