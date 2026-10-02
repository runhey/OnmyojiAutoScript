"""
Tests for ``_encode_value_check`` in ``oas.ext.algorithm.bit2coding``.

``_encode_value_check`` validates that input values are within the allowed range
for bit2 encoding.  Without ``ext8``, values must be 0-3; with ``ext8=True``,
values 0-7 are allowed.  Negative values are always rejected.
"""

from collections import deque

import pytest

from oas.ext.algorithm.bit2coding import _encode_value_check

# ==============================================================================
# Empty input — accepted without exception
# ==============================================================================


class TestEncodeValueCheckEmpty:
    """Empty input should return without raising."""

    def test_empty_list(self):
        """Empty list does not raise."""
        _encode_value_check([])

    def test_empty_deque(self):
        """Empty deque does not raise."""
        _encode_value_check(deque())

    def test_empty_list_with_ext8(self):
        """Empty list with ext8=True does not raise."""
        _encode_value_check([], ext8=True)

    def test_empty_deque_with_ext8(self):
        """Empty deque with ext8=True does not raise."""
        _encode_value_check(deque(), ext8=True)


# ==============================================================================
# Valid inputs — no exception expected
# ==============================================================================


class TestEncodeValueCheckValid:
    """Inputs with all values in the valid range should not raise."""

    @pytest.mark.parametrize("data", [
        [0],
        [3],
        [0, 1, 2, 3],
        [0, 0, 0, 0],
        [1, 2, 1, 2],
    ])
    def test_valid_data_no_ext8(self, data):
        """Valid 0-3 values without ext8 does not raise."""
        _encode_value_check(data)

    @pytest.mark.parametrize("data", [
        [0],
        [4],
        [7],
        [0, 4, 7, 3],
        [1, 2, 5, 6, 0],
    ])
    def test_valid_data_with_ext8(self, data):
        """Valid 0-7 values with ext8=True does not raise."""
        _encode_value_check(data, ext8=True)

    def test_all_boundary_valid_without_ext8(self):
        """Values exactly at the 0 and 3 boundaries, no ext8."""
        _encode_value_check([0])
        _encode_value_check([3])
        _encode_value_check([0, 3])

    def test_all_boundary_valid_with_ext8(self):
        """Values exactly at the 0 and 7 boundaries with ext8=True."""
        _encode_value_check([0], ext8=True)
        _encode_value_check([7], ext8=True)
        _encode_value_check([0, 7], ext8=True)

    def test_deque_input_accepted(self):
        """deque is accepted as a valid input type."""
        _encode_value_check(deque([0, 1, 2, 3]))

    def test_deque_input_accepted_with_ext8(self):
        """deque is accepted with ext8=True."""
        _encode_value_check(deque([4, 5, 6, 7]), ext8=True)


# ==============================================================================
# Negative values — always rejected
# ==============================================================================


class TestEncodeValueCheckNegative:
    """Negative values should always raise ValueError."""

    @pytest.mark.parametrize("data, expected_val", [
        ([-1], -1),
        ([-1, 0, 1, 2], -1),
        ([0, -5, 3], -5),
        ([-100], -100),
    ])
    def test_negative_values_without_ext8(self, data, expected_val):
        """Negative values raise ValueError without ext8."""
        with pytest.raises(ValueError) as exc_info:
            _encode_value_check(data)
        assert str(expected_val) in str(exc_info.value)
        assert "value must be >= 0" in str(exc_info.value)

    @pytest.mark.parametrize("data, expected_val", [
        ([-1], -1),
        ([4, -2, 7], -2),
        ([-100], -100),
    ])
    def test_negative_values_with_ext8(self, data, expected_val):
        """Negative values raise ValueError with ext8."""
        with pytest.raises(ValueError) as exc_info:
            _encode_value_check(data, ext8=True)
        assert str(expected_val) in str(exc_info.value)
        assert "value must be >= 0" in str(exc_info.value)

    def test_single_negative_first_element(self):
        """First element negative triggers the error immediately."""
        with pytest.raises(ValueError, match="-1"):
            _encode_value_check([-1, 0, 1, 2])


# ==============================================================================
# Values exceeding the upper bound
# ==============================================================================


class TestEncodeValueCheckUpperBound:
    """Values above the allowed maximum should raise ValueError."""

    @pytest.mark.parametrize("data, expected_val", [
        ([4], 4),
        ([0, 1, 4], 4),
        ([5, 2, 3], 5),
        ([10], 10),
    ])
    def test_exceeds_3_without_ext8(self, data, expected_val):
        """Value >3 without ext8 raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _encode_value_check(data)
        assert str(expected_val) in str(exc_info.value)
        assert "value must be <= 3" in str(exc_info.value)

    @pytest.mark.parametrize("data, expected_val", [
        ([8], 8),
        ([0, 7, 8], 8),
        ([10, 20], 20),
        ([255], 255),
    ])
    def test_exceeds_7_with_ext8(self, data, expected_val):
        """Value >7 with ext8=True raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _encode_value_check(data, ext8=True)
        assert str(expected_val) in str(exc_info.value)
        assert "value must be <= 7" in str(exc_info.value)

    def test_value_4_without_ext8_boundary(self):
        """Value 4 is the smallest value rejected without ext8."""
        with pytest.raises(ValueError, match="4"):
            _encode_value_check([4])

    def test_value_8_with_ext8_boundary(self):
        """Value 8 is the smallest value rejected with ext8."""
        with pytest.raises(ValueError, match="8"):
            _encode_value_check([8], ext8=True)

    def test_value_3_without_ext8_allowed(self):
        """Value 3 is the largest value allowed without ext8."""
        _encode_value_check([3])

    def test_value_7_with_ext8_allowed(self):
        """Value 7 is the largest value allowed with ext8."""
        _encode_value_check([7], ext8=True)

    def test_mixed_valid_and_invalid(self):
        """Data containing both valid and invalid values still raises."""
        with pytest.raises(ValueError) as exc_info:
            _encode_value_check([0, 1, 2, 3, 4])
        assert "value must be <= 3" in str(exc_info.value)


# ==============================================================================
# Large data — performance and correctness
# ==============================================================================


class TestEncodeValueCheckLarge:
    """Large inputs should be handled efficiently."""

    def test_large_valid_list(self):
        """Large list of valid values does not raise."""
        _encode_value_check([i % 4 for i in range(10000)])

    def test_large_valid_list_with_ext8(self):
        """Large list of valid 0-7 values with ext8 does not raise."""
        _encode_value_check([i % 8 for i in range(10000)], ext8=True)

    def test_large_list_with_negative_raises(self):
        """Large list containing a single negative value still raises."""
        data = [i % 4 for i in range(10000)]
        data[5000] = -1
        with pytest.raises(ValueError, match="-1"):
            _encode_value_check(data)

    def test_large_list_exceeding_bound_raises(self):
        """Large list with a value > threshold raises."""
        data = [i % 4 for i in range(10000)]
        data[9999] = 10
        with pytest.raises(ValueError, match="10"):
            _encode_value_check(data)

    def test_large_deque(self):
        """Large deque of valid values does not raise."""
        _encode_value_check(deque([2] * 10000))


# ==============================================================================
# Error message content
# ==============================================================================


class TestEncodeValueCheckErrorMessage:
    """Verify the exact error message format."""

    def test_negative_error_message(self):
        """Error message for negative values includes the offending value."""
        with pytest.raises(ValueError) as exc_info:
            _encode_value_check([-42])
        msg = str(exc_info.value)
        assert "-42" in msg
        assert "value must be >= 0" in msg

    def test_exceeds_3_error_message(self):
        """Error message for >3 includes the offending value."""
        with pytest.raises(ValueError) as exc_info:
            _encode_value_check([99])
        msg = str(exc_info.value)
        assert "99" in msg
        assert "value must be <= 3" in msg

    def test_exceeds_7_error_message(self):
        """Error message for >7 with ext8 includes the offending value."""
        with pytest.raises(ValueError) as exc_info:
            _encode_value_check([99], ext8=True)
        msg = str(exc_info.value)
        assert "99" in msg
        assert "value must be <= 7" in msg

    def test_ext8_disabled_message_does_not_mention_ext8(self):
        """Without ext8, the error message says 'ext8 is disabled'."""
        with pytest.raises(ValueError) as exc_info:
            _encode_value_check([5])
        msg = str(exc_info.value)
        assert "ext8 is disabled" in msg

    def test_ext8_enabled_message_mentions_ext8(self):
        """With ext8, the error message says 'ext8 is enabled'."""
        with pytest.raises(ValueError) as exc_info:
            _encode_value_check([9], ext8=True)
        msg = str(exc_info.value)
        assert "ext8 is enabled" in msg
