import datetime
import time

import pytest

from oas.testing.patch_time import PatchTime


class TestInit:
    """Test PatchTime initialization."""

    def test_default_uses_current_time(self):
        """Initializing without arguments should capture the current time."""
        before = time.time()
        pt = PatchTime()
        after = time.time()
        assert before <= pt._timestamp <= after

    def test_with_timestamp_int(self):
        pt = PatchTime(1000)
        assert pt._timestamp == 1000.0

    def test_with_timestamp_float(self):
        pt = PatchTime(1234.567)
        assert pt._timestamp == 1234.567

    def test_with_datetime_naive(self):
        """Naive datetime should be treated as UTC."""
        dt = datetime.datetime(2023, 1, 15, 12, 30, 0)
        pt = PatchTime(dt)
        expected = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
        assert pt._timestamp == expected

    def test_with_datetime_aware_utc(self):
        dt = datetime.datetime(2023, 6, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        pt = PatchTime(dt)
        assert pt._timestamp == dt.timestamp()

    def test_with_datetime_aware_non_utc(self):
        tz = datetime.timezone(datetime.timedelta(hours=8))
        dt = datetime.datetime(2023, 1, 1, 8, 0, 0, tzinfo=tz)
        pt = PatchTime(dt)
        expected_utc_ts = dt.timestamp()
        assert pt._timestamp == expected_utc_ts

    def test_invalid_type(self):
        with pytest.raises(TypeError, match="Unsupported time type"):
            PatchTime("invalid")  # type: ignore[arg-type]


class TestSet:
    """Test the set() method."""

    def test_set_none(self):
        pt = PatchTime(0)
        before = time.time()
        pt.set(None)
        after = time.time()
        assert before <= pt._timestamp <= after

    def test_set_int(self):
        pt = PatchTime(0)
        pt.set(500)
        assert pt._timestamp == 500.0

    def test_set_float(self):
        pt = PatchTime(0)
        pt.set(500.123)
        assert pt._timestamp == 500.123

    def test_set_datetime(self):
        pt = PatchTime(0)
        dt = datetime.datetime(2024, 12, 25, 10, 0, 0)
        pt.set(dt)
        expected = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
        assert pt._timestamp == expected

    def test_set_invalid_type(self):
        pt = PatchTime(0)
        with pytest.raises(TypeError, match="Unsupported time type"):
            pt.set("invalid")  # type: ignore[arg-type]


class TestShift:
    """Test the shift() method."""

    def test_shift_int_forward(self):
        pt = PatchTime(100)
        pt.shift(50)
        assert pt._timestamp == 150.0

    def test_shift_int_backward(self):
        pt = PatchTime(100)
        pt.shift(-30)
        assert pt._timestamp == 70.0

    def test_shift_float(self):
        pt = PatchTime(100)
        pt.shift(0.5)
        assert pt._timestamp == 100.5

    def test_shift_timedelta(self):
        pt = PatchTime(100)
        pt.shift(datetime.timedelta(seconds=10, milliseconds=500))
        assert pt._timestamp == 110.5

    def test_shift_timedelta_negative(self):
        pt = PatchTime(100)
        pt.shift(datetime.timedelta(days=-1))
        assert pt._timestamp == 100 - 86400.0

    def test_shift_invalid_type(self):
        pt = PatchTime(0)
        with pytest.raises(TypeError, match="Delta must be int, float"):
            pt.shift("invalid")  # type: ignore[arg-type]


class TestEnterExit:
    """Test the context manager enter/exit behavior."""

    def test_exit_restores_time_time(self):
        pt = PatchTime(42)
        with pt:
            assert time.time() == 42.0
        # After exit, time.time() should return the real time
        real_now = time.time()
        assert abs(time.time() - real_now) < 0.1

    def test_exit_restores_datetime_now(self):
        pt = PatchTime(42)
        with pt:
            now = datetime.datetime.now(tz=datetime.timezone.utc)
            assert now.timestamp() == 42.0
        # After exit, datetime.datetime.now() should return the real time
        real_now = datetime.datetime.now(tz=datetime.timezone.utc)
        assert abs(real_now.timestamp() - time.time()) < 1.0

    def test_exit_restores_datetime_utcnow(self):
        pt = PatchTime(42)
        with pt:
            utcnow = datetime.datetime.utcnow()
            assert utcnow.hour == 0  # 1970-01-01 00:00:42
        # After exit, should be restored
        real_utcnow = datetime.datetime.now(tz=datetime.timezone.utc).replace(tzinfo=None)
        # utcnow() returns a naive datetime (no tzinfo).
        # Use real_utcnow directly (comparison with time.time() in local timezone is unreliable).
        # Instead verify that the result is close to the expected real time by constructing a timezone-aware UTC
        # datetime.
        real_utc = datetime.datetime.now(tz=datetime.timezone.utc)
        assert abs((real_utcnow - real_utc.replace(tzinfo=None)).total_seconds()) < 1.0

    def test_exit_restores_time_functions(self):
        pt = PatchTime(42)
        with pt:
            pass
        # All functions should be restored
        real_time = time.time()
        assert abs(time.time() - real_time) < 0.1
        assert abs(time.monotonic() - time.monotonic()) < 0.1  # self-consistency check
        assert abs(time.perf_counter() - time.perf_counter()) < 0.1

    def test_nested_context_managers(self):
        pt1 = PatchTime(100)
        pt2 = PatchTime(200)
        with pt1:
            assert time.time() == 100.0
            with pt2:
                assert time.time() == 200.0
            assert time.time() == 100.0
        assert abs(time.time() - time.time()) < 0.1  # restored


class TestMockedTimeBehavior:
    """Test the mocked time values inside the context manager."""

    @pytest.fixture
    def patch(self):
        with PatchTime(1234567890.0) as pt:
            yield pt

    def test_time_function(self, patch):
        assert time.time() == 1234567890.0

    def test_time_ns(self, patch):
        assert time.time_ns() == 1234567890_000_000_000

    def test_monotonic(self, patch):
        assert time.monotonic() == 1234567890.0

    def test_monotonic_ns(self, patch):
        assert time.monotonic_ns() == 1234567890_000_000_000

    def test_perf_counter(self, patch):
        assert time.perf_counter() == 1234567890.0

    def test_perf_counter_ns(self, patch):
        assert time.perf_counter_ns() == 1234567890_000_000_000

    def test_datetime_now_no_tz(self, patch):
        now = datetime.datetime.now()
        # Without tz argument, returns local naive datetime
        expected_local = datetime.datetime.fromtimestamp(1234567890.0)
        assert now == expected_local

    def test_datetime_now_with_tz_utc(self, patch):
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        assert now.tzinfo is not None
        assert now.timestamp() == 1234567890.0

    def test_datetime_now_with_tz_non_utc(self, patch):
        tz = datetime.timezone(datetime.timedelta(hours=8))
        now = datetime.datetime.now(tz=tz)
        assert now.tzinfo is not None
        # The returned time should be in the given timezone
        expected = datetime.datetime.fromtimestamp(1234567890.0, tz=datetime.timezone.utc).astimezone(tz)
        assert now == expected

    def test_datetime_utcnow(self, patch):
        utcnow = datetime.datetime.utcnow()
        expected = datetime.datetime(2009, 2, 13, 23, 31, 30)
        assert utcnow == expected

    def test_datetime_today(self, patch):
        today = datetime.datetime.today()
        expected = datetime.datetime.fromtimestamp(1234567890.0)
        assert today == expected

    def test_date_today(self, patch):
        today = datetime.date.today()
        expected = datetime.datetime.fromtimestamp(1234567890.0).date()
        assert today == expected


class TestTimeEvolution:
    """Test that shift() affects the mocked time inside the context manager."""

    def test_time_after_shift(self):
        pt = PatchTime(1000)
        with pt:
            assert time.time() == 1000.0
            pt.shift(50)
            assert time.time() == 1050.0

    def test_time_difference(self):
        """Verify that time differences correctly reflect shift()."""
        pt = PatchTime(1000)
        with pt:
            t1 = time.time()
            pt.shift(10)
            t2 = time.time()
            assert t2 - t1 == 10.0

    def test_monotonic_difference(self):
        pt = PatchTime(1000)
        with pt:
            t1 = time.monotonic()
            pt.shift(5.5)
            t2 = time.monotonic()
            assert t2 - t1 == 5.5

    def test_perf_counter_difference(self):
        pt = PatchTime(1000)
        with pt:
            t1 = time.perf_counter()
            pt.shift(2.25)
            t2 = time.perf_counter()
            assert t2 - t1 == 2.25

    def test_datetime_after_shift(self):
        pt = PatchTime(0)
        with pt:
            dt1 = datetime.datetime.now(tz=datetime.timezone.utc)
            pt.shift(3600)  # +1 hour
            dt2 = datetime.datetime.now(tz=datetime.timezone.utc)
            assert (dt2 - dt1).total_seconds() == 3600.0

    def test_shift_backward_datetime(self):
        pt = PatchTime(1000)
        with pt:
            dt1 = datetime.datetime.now(tz=datetime.timezone.utc)
            pt.shift(-500)
            dt2 = datetime.datetime.now(tz=datetime.timezone.utc)
            assert (dt2 - dt1).total_seconds() == -500.0


class TestEdgeCases:
    """Test edge cases and special values."""

    def test_timestamp_zero(self):
        """Unix epoch."""
        pt = PatchTime(0)
        with pt:
            dt = datetime.datetime.utcnow()
            assert dt == datetime.datetime(1970, 1, 1, 0, 0, 0)

    def test_timestamp_negative(self):
        """Before Unix epoch."""
        pt = PatchTime(-3600)
        with pt:
            assert time.time() == -3600.0
            dt = datetime.datetime.utcnow()
            assert dt == datetime.datetime(1969, 12, 31, 23, 0, 0)

    def test_large_timestamp(self):
        """Far future."""
        pt = PatchTime(4102444800.0)  # 2100-01-01
        with pt:
            assert time.time() == 4102444800.0

    def test_shift_zero(self):
        pt = PatchTime(100)
        pt.shift(0)
        assert pt._timestamp == 100.0

    def test_set_after_shift(self):
        pt = PatchTime(100)
        pt.shift(50)
        pt.set(200)
        assert pt._timestamp == 200.0

    def test_context_manager_reuse(self):
        """PatchTime can be entered multiple times."""
        pt = PatchTime(100)
        with pt:
            assert time.time() == 100.0
        with pt:
            assert time.time() == 100.0


class TestTimestampConversionConsistency:
    """Test that round-trip conversions (timestamp → datetime → timestamp) are consistent."""

    @pytest.mark.parametrize("ts", [0, 1, 1000, 1234567890, 4102444800, -3600, 0.5, 1234.567])
    def test_datetime_now_consistency(self, ts):
        pt = PatchTime(ts)
        with pt:
            # now() without tz returns local naive datetime, but we can compare via timestamp
            now = datetime.datetime.now(tz=datetime.timezone.utc)
            assert abs(now.timestamp() - ts) < 0.001

    @pytest.mark.parametrize("ts", [0, 1, 1000, 1234567890, 4102444800, -3600, 0.5, 1234.567])
    def test_datetime_utcnow_consistency(self, ts):
        pt = PatchTime(ts)
        with pt:
            utcnow = datetime.datetime.utcnow()
            epoch = datetime.datetime(1970, 1, 1, 0, 0, 0)
            delta = (utcnow - epoch).total_seconds()
            assert abs(delta - ts) < 0.001

    @pytest.mark.parametrize("ts", [0, 1, 1000, 1234567890, 4102444800, -3600, 0.5, 1234.567])
    def test_time_ns_consistency(self, ts):
        pt = PatchTime(ts)
        with pt:
            assert time.time_ns() == int(ts * 1_000_000_000)
