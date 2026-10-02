import datetime

import pytest

import oas.ext.timez as time_converter
from oas.ext.timez import to_local_aware, to_local_naive


@pytest.fixture
def mock_local_tz(monkeypatch):
    """
    Mocks the _get_local_tz helper function to return a fixed timezone.
    This is the definitive, robust way to handle this testing challenge.
    """
    fixed_tz = datetime.timezone(datetime.timedelta(hours=8), name="CST")

    # A simple mock function that replaces our helper
    def mock_get_local_tz():
        return fixed_tz

    monkeypatch.setattr(time_converter, 'get_local_tz', mock_get_local_tz)

    # Still return the tz object so our tests can use it for assertions.
    return fixed_tz


# --- Systematic Test Case Generation ---

def generate_test_cases():
    """Generates a comprehensive list of test cases covering all permutations."""
    MOCKED_LOCAL_TZ = datetime.timezone(datetime.timedelta(hours=8), "CST")
    OTHER_TZ_NEG = datetime.timezone(datetime.timedelta(hours=-5), "EST")
    OTHER_TZ_POS = datetime.timezone(datetime.timedelta(hours=2), "CET")

    # Define base scenarios: without and with milliseconds
    scenarios = [
        # (suffix, base_utc_dt, expected_naive, expected_aware)
        (
            "",
            datetime.datetime(2023, 11, 22, 10, 30, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2023, 11, 22, 18, 30, 0),
            datetime.datetime(2023, 11, 22, 18, 30, 0, tzinfo=MOCKED_LOCAL_TZ)
        ),
        (
            "_ms",
            datetime.datetime(2023, 11, 22, 10, 30, 0, 123456, tzinfo=datetime.timezone.utc),
            datetime.datetime(2023, 11, 22, 18, 30, 0, 123456),
            datetime.datetime(2023, 11, 22, 18, 30, 0, 123456, tzinfo=MOCKED_LOCAL_TZ)
        )
    ]

    all_cases = []
    for suffix, base_dt, exp_naive, exp_aware in scenarios:
        # 1. Datetime object inputs
        all_cases.extend([
            ("aware_dt_utc" + suffix, base_dt, exp_naive, exp_aware),
            ("aware_dt_neg_tz" + suffix, base_dt.astimezone(OTHER_TZ_NEG), exp_naive, exp_aware),
            ("aware_dt_pos_tz" + suffix, base_dt.astimezone(OTHER_TZ_POS), exp_naive, exp_aware),
            ("naive_dt" + suffix, exp_naive, exp_naive, exp_aware),
        ])

        # 2. String inputs (permutations of separator and timezone format)
        for sep in ["T", " "]:
            sep_id = "_space" if sep == " " else "_T"

            # UTC formats
            utc_z_str = base_dt.isoformat(sep=sep).replace("+00:00", "Z")
            utc_offset_str = base_dt.isoformat(sep=sep)
            all_cases.extend([
                ("utc_str_z" + sep_id + suffix, utc_z_str, exp_naive, exp_aware),
                ("utc_str_offset" + sep_id + suffix, utc_offset_str, exp_naive, exp_aware),
            ])

            # Other timezone formats
            neg_tz_str = base_dt.astimezone(OTHER_TZ_NEG).isoformat(sep=sep)
            pos_tz_str = base_dt.astimezone(OTHER_TZ_POS).isoformat(sep=sep)
            all_cases.extend([
                ("neg_tz_str" + sep_id + suffix, neg_tz_str, exp_naive, exp_aware),
                ("pos_tz_str" + sep_id + suffix, pos_tz_str, exp_naive, exp_aware),
            ])

            # Naive string format
            naive_str = exp_naive.isoformat(sep=sep)
            all_cases.append(("naive_str" + sep_id + suffix, naive_str, exp_naive, exp_aware))

    return all_cases


TEST_CASES = generate_test_cases()
TEST_IDS = [case[0] for case in TEST_CASES]


# --- Test Class ---

@pytest.mark.usefixtures("mock_local_tz")
class TestTimeConverter:

    @pytest.mark.parametrize("test_id, time_input, expected_naive, expected_aware", TEST_CASES, ids=TEST_IDS)
    def test_to_local_naive(self, test_id, time_input, expected_naive, expected_aware):
        """Tests that to_local_naive correctly converts all input permutations."""
        result = to_local_naive(time_input)
        assert result == expected_naive
        assert result.tzinfo is None, "Result must be a naive datetime object"

    @pytest.mark.parametrize("test_id, time_input, expected_naive, expected_aware", TEST_CASES, ids=TEST_IDS)
    def test_to_local_aware(self, test_id, time_input, expected_naive, expected_aware):
        """Tests that to_local_aware correctly converts all input permutations."""
        result = to_local_aware(time_input)
        assert result == expected_aware
        assert result.tzinfo is not None, "Result must be an aware datetime object"

    @pytest.mark.parametrize("test_id, time_input, expected_naive, expected_aware", TEST_CASES, ids=TEST_IDS)
    def test_string_serialization_round_trip(self, test_id, time_input, expected_naive, expected_aware):
        """
        Tests that converting a string input, re-serializing to a string, and converting
        back again produces a stable and correct result.
        """
        if not isinstance(time_input, str):
            pytest.skip("This test is only for string inputs.")

        # First conversion: Input String -> Aware Datetime
        aware_dt_1 = to_local_aware(time_input)
        assert aware_dt_1 == expected_aware

        # Second step: Aware Datetime -> ISO String
        # The output format is standardized by .isoformat()
        iso_str_output = aware_dt_1.isoformat()

        # Third conversion: ISO String -> Naive Datetime
        # This simulates another system receiving the standardized string
        naive_dt_2 = to_local_naive(iso_str_output)
        assert naive_dt_2 == expected_naive

        # Final conversion: Naive String representation -> Aware Datetime
        # Check if a naive string can be correctly re-localized
        naive_str_output = naive_dt_2.isoformat()
        aware_dt_3 = to_local_aware(naive_str_output)
        assert aware_dt_3 == expected_aware

    def test_invalid_type_raises_error(self):
        """Tests that a TypeError is raised for invalid input types."""
        with pytest.raises(TypeError, match="Input must be a str or datetime.datetime object"):
            to_local_naive(12345)
        with pytest.raises(TypeError, match="Input must be a str or datetime.datetime object"):
            to_local_aware([2023, 11, 22])

    def test_invalid_string_format_raises_error(self):
        """Tests that a ValueError is raised for non-ISO formatted strings."""
        with pytest.raises(ValueError):
            to_local_naive("22-11-2023 10:30:00")
        with pytest.raises(ValueError):
            to_local_aware("not a time string")
