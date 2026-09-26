import time

import pytest

from oas.testing.patch_time import PatchTime
from oas.testing.timeout import AssertTimeout


def test_immediate_success():
    """Test that the loop exits immediately if the assertion passes."""
    with PatchTime(100.0):
        start = time.perf_counter()
        count = 0
        for _ in AssertTimeout(timeout=1.0):
            with _:
                count += 1
                assert True
        end = time.perf_counter()

    assert count == 1
    assert end - start < 0.1  # Should be very fast (no retries)


def test_eventual_success():
    """Test that the loop retries until success within timeout."""
    with PatchTime(100.0):
        start = time.perf_counter()
        count = 0
        target = 3

        # It will fail for the first 2 times, and pass on the 3rd time
        for _ in AssertTimeout(timeout=1.0, interval=0.01):
            with _:
                count += 1
                if count < target:
                    assert False, "Not yet"
                assert True

        end = time.perf_counter()

    assert count == target
    # Should have taken at least (target-1) * interval in mock time
    # Each of the first (target-1) iterations sleeps for interval via mock_sleep
    assert end - start >= (target - 1) * 0.01


def test_timeout_failure():
    """Test that AssertionError is raised if it never passes within timeout."""
    timeout = 0.1

    with PatchTime(100.0):
        start = time.perf_counter()

        with pytest.raises(AssertionError, match="Always fail"):
            for _ in AssertTimeout(timeout=timeout, interval=0.01):
                with _:
                    assert False, "Always fail"

        end = time.perf_counter()

    # mock time should have advanced by at least the timeout
    assert end - start >= timeout


def test_other_exception_propagation():
    """Test that non-AssertionErrors are propagated immediately."""
    with PatchTime(100.0):
        start = time.perf_counter()
        count = 0

        with pytest.raises(ValueError, match="Something wrong"):
            for _ in AssertTimeout(timeout=1.0, interval=0.01):
                with _:
                    count += 1
                    raise ValueError("Something wrong")

        end = time.perf_counter()

    assert count == 1
    assert end - start < 0.1  # Should not retry (no mock sleep advance)
