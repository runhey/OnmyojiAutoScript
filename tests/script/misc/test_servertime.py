import calendar
from datetime import datetime, timedelta, timezone, tzinfo
from unittest.mock import patch

import pytest

from script.misc import servertime
from script.misc.servertime import (
    ServerTime, ServerUpdateCondition, nearest_future, parse_second, parse_server_update, parse_server_update_list,
    parse_timezone, random_time
)
from oas.testing.patch_time import PatchTime


class TestParseTimezone:
    @pytest.mark.parametrize("input_val, expected_offset_hours, expected_offset_minutes", [
        # Test cases for timezone objects
        (timezone.utc, 0, 0),
        (timezone(timedelta(hours=8)), 8, 0),

        # Test cases for timedelta objects
        (timedelta(hours=-5), -5, 0),
        (timedelta(hours=3, minutes=30), 3, 30),

        # Test cases for integers
        (8, 8, 0),
        (-7, -7, 0),
        (0, 0, 0),

        # Test cases for strings (HH:MM format)
        ("09:30", 9, 30),
        ("-05:00", -5, 0),
        ("0:0", 0, 0),

        # Test cases for strings (Single integer format)
        ("8", 8, 0),
        ("-7", -7, 0),
        ("0", 0, 0),
    ])
    def test_parse_timezone_success(self, input_val, expected_offset_hours, expected_offset_minutes):
        """Test successful conversion for all supported types and formats."""
        result = parse_timezone(input_val)
        assert isinstance(result, timezone)

        expected_delta = timedelta(hours=expected_offset_hours, minutes=expected_offset_minutes)
        assert result.utcoffset(None) == expected_delta

    @pytest.mark.parametrize("invalid_input, match_msg", [
        # timedelta out of range
        (timedelta(hours=30), "offset must be a timedelta strictly between"),

        # Integer out of range
        (24, "Timezone hour must within -23~23"),
        (-25, "Timezone hour must within -23~23"),

        # String HH:MM out of range or invalid
        ("25:00", "Timezone hour must within -23~23"),
        ("05:61", "Timezone hour must within 0~59"),
        ("abc:00", "Failed to parse timezone as HH:MM"),

        # String integer out of range or invalid
        ("24", "Timezone hour must within -23~23"),
        ("xyz", "Failed to parse timezone as hour"),

        # Invalid types
        (1.5, "Invalid timezone input"),
        (None, "Invalid timezone input"),
        ([], "Invalid timezone input"),
    ])
    def test_parse_timezone_exceptions(self, invalid_input, match_msg):
        """Test that invalid inputs raise ValueError with appropriate messages."""
        with pytest.raises(ValueError, match=match_msg):
            parse_timezone(invalid_input)

    def test_identity_check(self):
        """Ensure that if a timezone object is passed, the same object (or equivalent) is returned."""
        tz = timezone(timedelta(hours=2))
        assert parse_timezone(tz) is tz


class TestParseServerUpdate:
    @pytest.mark.parametrize("input_val, expected", [
        ("12:34", ServerUpdateCondition(hour=12, minute=34)),
        ("18", ServerUpdateCondition(hour=18, minute=0)),
        (18, ServerUpdateCondition(hour=18, minute=0)),
        ("weekday1-04:00", ServerUpdateCondition(weekday=1, hour=4, minute=0)),
        ("monthday1-04:00", ServerUpdateCondition(monthday=1, hour=4, minute=0)),
        (" weekday 2 - 05 : 30 ", ServerUpdateCondition(weekday=2, hour=5, minute=30)),
    ])
    def test_parse_server_update_success(self, input_val, expected):
        """Test valid inputs for parse_server_update."""
        assert parse_server_update(input_val) == expected

    @pytest.mark.parametrize("invalid_input, match_msg", [
        (25, "ServerUpdate hour must within 0~23"),
        (-1, "ServerUpdate hour must within 0~23"),
        ("", "Empty server_update"),
        (" ", "Empty server_update"),
        ("weekday0-04:00", "Weekday must within 1~7"),
        ("weekday8-04:00", "Weekday must within 1~7"),
        ("weekday-04:00", "Failed to parse weekday"),
        ("monthday0-04:00", "Monthday must within 1~31"),
        ("monthday32-04:00", "Monthday must within 1~31"),
        ("monthday-04:00", "Failed to parse monthday"),
        ("12:60", "Minute must within 0~59"),
        ("24:00", "Hour must within 0~23"),
        ("abc:00", "Failed to parse time"),
        ("weekday1", "Hour and minute must be set"),
        ("monthday1", "Hour and minute must be set"),
        ("weekday1-monthday1-04:00", "Cannot have both weekday and monthday"),
        ("-", "Failed to parse time"),
        (None, "Invalid server_update input"),
    ])
    def test_parse_server_update_exceptions(self, invalid_input, match_msg):
        """Test invalid inputs for parse_server_update."""
        with pytest.raises(ValueError, match=match_msg):
            parse_server_update(invalid_input)


class TestParseServerUpdateList:
    def test_parse_server_update_list_success(self):
        # Single input
        assert parse_server_update_list("12:00") == [ServerUpdateCondition(hour=12, minute=0)]
        assert parse_server_update_list(12) == [ServerUpdateCondition(hour=12, minute=0)]

        # List input
        updates = ["18:00", "04:00"]
        expected = [
            ServerUpdateCondition(hour=4, minute=0),
            ServerUpdateCondition(hour=18, minute=0)
        ]
        assert parse_server_update_list(updates) == expected

        # Weekday/Monthday sorting
        # Daily < Weekly < Monthly
        updates = ["monthday2-04:00", "weekday1-04:00", "04:00"]
        expected = [
            ServerUpdateCondition(hour=4, minute=0),
            ServerUpdateCondition(weekday=1, hour=4, minute=0),
            ServerUpdateCondition(monthday=2, hour=4, minute=0),
        ]
        assert parse_server_update_list(updates) == expected

    def test_parse_server_update_list_exceptions(self):
        with pytest.raises(ValueError, match="Empty server_update input"):
            parse_server_update_list([])
        # Note: None input is caught in parse_server_update
        with pytest.raises(ValueError, match="Invalid server_update input"):
            parse_server_update_list(None)


class TestNearestFuture:
    def test_empty_list_raises_error(self):
        with pytest.raises(ValueError, match="Empty future list"):
            nearest_future([])

    def test_single_element(self):
        now = datetime(2023, 1, 1, 12, 0, 0)
        assert nearest_future([now]) == now
        assert nearest_future([now], threshold=60) == now

    def test_threshold_logic(self):
        base = datetime(2023, 1, 1, 12, 0, 0)
        d2 = base + timedelta(seconds=10)
        d3 = base + timedelta(seconds=20)
        d4 = base + timedelta(seconds=30)

        # threshold=0
        assert nearest_future([d3, base, d2], threshold=0) == base

        # threshold=15
        assert nearest_future([base, d2, d3], threshold=15) == d2

        # threshold=25
        assert nearest_future([base, d2, d3, d4], threshold=25) == d3


class TestParseSecond:
    @pytest.mark.parametrize("input_val, expected", [
        (3, (3, 3)),
        (0, (0, 0)),
        (10.5, (10.5, 10.5)),
        (0.5, (0.5, 0.5)),
        ("3", (3, 3)),
        (" 10 ", (10, 10)),
        ("0.1~0.2", (0.1, 0.2)),
        ("1.5, 2.5", (1.5, 2.5)),
        ((1, 4), (1, 4)),
        ([5, 10], (5, 10)),
        ((1.5, 2.5), (1.5, 2.5)),
        ([0.5, 1.5], (0.5, 1.5)),
        ("10~30", (10, 30)),
        ("10, 30", (10, 30)),
        ("10-30", (10, 30)),
    ])
    def test_parse_second_valid(self, input_val, expected):
        assert parse_second(input_val) == expected

    def test_parse_second_exceptions(self):
        with pytest.raises(ValueError, match="Second must >=0"):
            parse_second(-5)
        with pytest.raises(ValueError, match="Second must >=0"):
            parse_second("-10")
        with pytest.raises(ValueError, match="Expect format"):
            parse_second([1])
        with pytest.raises(ValueError, match="High bound must >= lower bound"):
            parse_second("30-10")
        with pytest.raises(ValueError, match="Low bound and high bound must be numeric"):
            parse_second("10-abc")
        with pytest.raises(ValueError, match="Invalid second input"):
            parse_second(None)


@pytest.fixture
def server():
    # Use UTC+8 as default server timezone
    return ServerTime(tz=8)


def to_utc(dt):
    """Normalize datetime to UTC for comparison."""
    return dt.astimezone(timezone.utc)


class TestNow:
    """Tests for ServerTime.now()."""

    def test_now(self, server):
        now = server.now()
        # Should have the correct timezone
        assert now.tzinfo == server.tz

    def test_now_weekday_server_tz(self, server):
        """
        server.now().weekday() should return the weekday in the server timezone,
        not the local timezone.
        """

        # Choose a UTC moment where server timezone (UTC+8) has a different weekday.
        # 2026-06-26 17:00 UTC = Friday (weekday=4)
        # 2026-06-27 01:00 UTC+8 = Saturday (weekday=5)
        utc_dt = datetime(2026, 6, 26, 17, 0, tzinfo=timezone.utc)
        server_dt = utc_dt.astimezone(server.tz)

        # Verify the weekday differs between timezones at this moment
        assert utc_dt.weekday() == 4  # Friday in UTC
        assert server_dt.weekday() == 5  # Saturday in server tz

        with PatchTime(server_dt):
            result = server.now()
            assert result.weekday() == 5, (
                f"Expected weekday=5 (Saturday) in server tz, got {result.weekday()}. "
                f"If local timezone (UTC) were used, weekday would be {utc_dt.weekday()}"
            )


class TestIsValidDate:
    """Tests for ServerTime._is_valid_date()."""

    def test_is_valid_date(self, server):
        assert server._is_valid_date(2023, 1, 31) is True
        assert server._is_valid_date(2023, 2, 28) is True
        assert server._is_valid_date(2024, 2, 29) is True
        assert server._is_valid_date(2023, 2, 29) is False
        assert server._is_valid_date(2023, 4, 31) is False
        assert server._is_valid_date(2023, 13, 1) is False
        assert server._is_valid_date(2023, 0, 1) is False


class TestGetOccurrence:
    """Tests for ServerTime._get_occurrence()."""

    def test_daily(self, server):
        # 10:00 today, daily update at 09:00 -> should be 09:00 tomorrow
        now = datetime(2023, 1, 1, 10, 0, tzinfo=server.tz)
        cond = ServerUpdateCondition(hour=9, minute=0)

        # Future
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 1, 2, 9, 0, tzinfo=server.tz)

        # Past
        res = server._get_occurrence(cond, now, direction=-1)
        assert res == datetime(2023, 1, 1, 9, 0, tzinfo=server.tz)

        # 08:00 today, daily update at 09:00 -> should be 09:00 today
        now = datetime(2023, 1, 1, 8, 0, tzinfo=server.tz)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 1, 1, 9, 0, tzinfo=server.tz)

        res = server._get_occurrence(cond, now, direction=-1)
        assert res == datetime(2022, 12, 31, 9, 0, tzinfo=server.tz)

    def test_weekly(self, server):
        # 2023-01-02 is Monday (1)
        now = datetime(2023, 1, 2, 10, 0, tzinfo=server.tz)

        # Target Monday 09:00 (passed today) -> Next is next Monday
        cond = ServerUpdateCondition(weekday=1, hour=9, minute=0)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 1, 9, 9, 0, tzinfo=server.tz)

        # Past is today 09:00
        res = server._get_occurrence(cond, now, direction=-1)
        assert res == datetime(2023, 1, 2, 9, 0, tzinfo=server.tz)

        # Target Wednesday (3) 09:00 -> Next is this Wednesday
        cond = ServerUpdateCondition(weekday=3, hour=9, minute=0)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 1, 4, 9, 0, tzinfo=server.tz)

        # Past is last Wednesday
        res = server._get_occurrence(cond, now, direction=-1)
        assert res == datetime(2022, 12, 28, 9, 0, tzinfo=server.tz)

    def test_monthly(self, server):
        # 2023-01-20, target 1st
        now = datetime(2023, 1, 20, 10, 0, tzinfo=server.tz)
        cond = ServerUpdateCondition(monthday=1, hour=9, minute=0)

        # Next is Feb 1st
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 2, 1, 9, 0, tzinfo=server.tz)

        # Past is Jan 1st
        res = server._get_occurrence(cond, now, direction=-1)
        assert res == datetime(2023, 1, 1, 9, 0, tzinfo=server.tz)

        # Target 31st, starting from Feb 1st
        now = datetime(2023, 2, 1, 10, 0, tzinfo=server.tz)
        cond = ServerUpdateCondition(monthday=31, hour=9, minute=0)

        # Next is Mar 31 (Feb doesn't have 31)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 3, 31, 9, 0, tzinfo=server.tz)

        # Past is Jan 31
        res = server._get_occurrence(cond, now, direction=-1)
        assert res == datetime(2023, 1, 31, 9, 0, tzinfo=server.tz)

        # Leap year: 2024-02-29
        now = datetime(2024, 2, 1, 10, 0, tzinfo=server.tz)
        cond = ServerUpdateCondition(monthday=29, hour=9, minute=0)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2024, 2, 29, 9, 0, tzinfo=server.tz)

        # Non-leap year: 2023-02-29 -> skips to next month with 29th
        now = datetime(2023, 2, 1, 10, 0, tzinfo=server.tz)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 3, 29, 9, 0, tzinfo=server.tz)

    def test_invalid_monthday(self, server):
        cond = ServerUpdateCondition(monthday=100, hour=9, minute=0)
        with pytest.raises(ValueError, match="Invalid monthday setting"):
            server._get_occurrence(cond, server.now())

    def test_minutes_only(self, server):
        """
        Minutes-only condition (hour=None, minute=30) means updates every hour
        at minute 30.
        """
        cond = ServerUpdateCondition(minute=30)

        # Direction=1: before the :30 mark → same hour
        now = datetime(2023, 1, 1, 10, 15, tzinfo=server.tz)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 1, 1, 10, 30, tzinfo=server.tz)

        # Direction=1: after the :30 mark → next hour
        now = datetime(2023, 1, 1, 10, 45, tzinfo=server.tz)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 1, 1, 11, 30, tzinfo=server.tz)

        # Direction=1: exactly at :30 → next hour
        now = datetime(2023, 1, 1, 10, 30, tzinfo=server.tz)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 1, 1, 11, 30, tzinfo=server.tz)

        # Direction=-1: before the :30 mark → previous hour
        now = datetime(2023, 1, 1, 10, 15, tzinfo=server.tz)
        res = server._get_occurrence(cond, now, direction=-1)
        assert res == datetime(2023, 1, 1, 9, 30, tzinfo=server.tz)

        # Direction=-1: after the :30 mark → same hour
        now = datetime(2023, 1, 1, 10, 45, tzinfo=server.tz)
        res = server._get_occurrence(cond, now, direction=-1)
        assert res == datetime(2023, 1, 1, 10, 30, tzinfo=server.tz)

        # Direction=-1: exactly at :30 → same hour
        now = datetime(2023, 1, 1, 10, 30, tzinfo=server.tz)
        res = server._get_occurrence(cond, now, direction=-1)
        assert res == datetime(2023, 1, 1, 10, 30, tzinfo=server.tz)

        # Crossing midnight
        now = datetime(2023, 1, 1, 0, 15, tzinfo=server.tz)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 1, 1, 0, 30, tzinfo=server.tz)

        now = datetime(2023, 1, 1, 0, 45, tzinfo=server.tz)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 1, 1, 1, 30, tzinfo=server.tz)

    def test_weekday_minute_no_hour(self, server):
        """
        A condition with weekday/minute but no hour should NOT be treated as
        every-hour — it falls through to the weekly branch with hour=0.
        """
        # 2023-01-02 is Monday (weekday=1), 10:15
        now = datetime(2023, 1, 2, 10, 15, tzinfo=server.tz)
        cond = ServerUpdateCondition(weekday=1, minute=30)

        # Should be next Monday at 00:30 (every-hour branch would give 10:30)
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 1, 9, 0, 30, tzinfo=server.tz)

        # Past should be this Monday at 00:30 (already passed)
        res = server._get_occurrence(cond, now, direction=-1)
        assert res == datetime(2023, 1, 2, 0, 30, tzinfo=server.tz)

    def test_minutes_only_requires_monthday_weekday_none(self, server):
        """
        Minutes-only is only triggered when both monthday and weekday are None.
        A condition with monthday set but no hour should use the monthly branch.
        """
        now = datetime(2023, 1, 15, 10, 0, tzinfo=server.tz)
        cond = ServerUpdateCondition(monthday=1, minute=30)

        # Should be Feb 1st 00:30, not Jan 15th 10:30
        res = server._get_occurrence(cond, now, direction=1)
        assert res == datetime(2023, 2, 1, 0, 30, tzinfo=server.tz)

    def test_empty_condition(self, server):
        """An empty ServerUpdateCondition (all fields None) returns None."""
        cond = ServerUpdateCondition()
        now = datetime(2023, 1, 1, 10, 0, tzinfo=server.tz)
        assert server._get_occurrence(cond, now, direction=1) is None
        assert server._get_occurrence(cond, now, direction=-1) is None


class TestGetNextUpdate:
    """Tests for ServerTime.get_next_update()."""

    def test_filters_none(self, server):
        """Empty conditions are filtered out without crashing."""
        now = datetime(2023, 1, 1, 10, 0, tzinfo=server.tz)
        updates = [
            ServerUpdateCondition(hour=12, minute=0),
            ServerUpdateCondition(),  # empty → None
        ]
        with patch.object(ServerTime, 'now', return_value=now):
            next_update = server.get_next_update(updates)
            assert to_utc(next_update) == to_utc(datetime(2023, 1, 1, 12, 0, tzinfo=server.tz))

    def test_empty_raises_error(self, server):
        """Raises when all conditions produce no candidates."""
        now = datetime(2023, 1, 1, 10, 0, tzinfo=server.tz)
        with patch.object(ServerTime, 'now', return_value=now):
            with pytest.raises(ValueError, match='No valid candidates'):
                server.get_next_update([ServerUpdateCondition()])


class TestGetLastUpdate:
    """Tests for ServerTime.get_last_update()."""

    def test_filters_none(self, server):
        """Empty conditions are filtered out without crashing."""
        now = datetime(2023, 1, 1, 10, 0, tzinfo=server.tz)
        updates = [
            ServerUpdateCondition(hour=12, minute=0),
            ServerUpdateCondition(),  # empty → None
        ]
        with patch.object(ServerTime, 'now', return_value=now):
            last_update = server.get_last_update(updates)
            assert to_utc(last_update) == to_utc(datetime(2022, 12, 31, 12, 0, tzinfo=server.tz))

    def test_empty_raises_error(self, server):
        """Raises when all conditions produce no candidates."""
        now = datetime(2023, 1, 1, 10, 0, tzinfo=server.tz)
        with patch.object(ServerTime, 'now', return_value=now):
            with pytest.raises(ValueError, match='No valid candidates'):
                server.get_last_update([ServerUpdateCondition()])


class TestGetDeltaToUpdate:
    """Tests for ServerTime.get_delta_to_update()."""

    def test_nearest_future(self, server):
        """
        When ``now`` is closer to the next update than the last,
        the delta should be positive (future).
        """
        # Server updates at 00:00, 12:00. Now is 10:00.
        # Last was 00:00 (10h ago), next is 12:00 (2h later).
        # Nearest is 12:00 → delta = +2h
        now = datetime(2023, 1, 1, 10, 0, tzinfo=server.tz)
        with patch.object(ServerTime, 'now', return_value=now):
            delta = server.get_delta_to_update("00:00, 12:00")
            assert delta is not None
            assert delta.total_seconds() == 2 * 3600  # +2 hours

    def test_nearest_past(self, server):
        """
        When ``now`` is closer to the last update than the next,
        the delta should be negative (past).
        """
        # Server updates at 00:00, 12:00. Now is 13:00.
        # Last was 12:00 (1h ago), next is tomorrow 00:00 (11h later).
        # Nearest is 12:00 → delta = -1h
        now = datetime(2023, 1, 1, 13, 0, tzinfo=server.tz)
        with patch.object(ServerTime, 'now', return_value=now):
            delta = server.get_delta_to_update("00:00, 12:00")
            assert delta is not None
            assert delta.total_seconds() == -1 * 3600  # -1 hour

    def test_midway(self, server):
        """
        When ``now`` is exactly midway between two daily updates,
        both directions have the same distance.
        """
        # Server updates at 00:00, 12:00. Now is 06:00.
        # Next 12:00 is +6h, last 00:00 was -6h.
        # Both are 6h away; the first in the candidate list wins.
        now = datetime(2023, 1, 1, 6, 0, tzinfo=server.tz)
        with patch.object(ServerTime, 'now', return_value=now):
            delta = server.get_delta_to_update("00:00, 12:00")
            assert delta is not None
            assert abs(delta.total_seconds()) == 6 * 3600  # 6 hours

    def test_minutes_only(self, server):
        """
        Minutes-only condition (every hour) — nearest could be
        a few minutes away in either direction.
        """
        # Now is 10:35, every hour at :30.
        # Last was 10:30 (5min ago), next is 11:30 (55min later).
        # Nearest is 10:30 → delta = -5min
        now = datetime(2023, 1, 1, 10, 35, tzinfo=server.tz)
        cond = ServerUpdateCondition(minute=30)
        with patch.object(ServerTime, 'now', return_value=now):
            delta = server.get_delta_to_update([cond])
            assert delta is not None
            assert delta.total_seconds() == -5 * 60  # -5 minutes

    def test_empty_condition(self, server):
        """Empty conditions should raise ValueError."""
        now = datetime(2023, 1, 1, 10, 0, tzinfo=server.tz)
        with patch.object(ServerTime, 'now', return_value=now):
            with pytest.raises(ValueError, match='No valid candidates'):
                server.get_delta_to_update([ServerUpdateCondition()])


class TestServerUpdateComplex:
    @pytest.mark.parametrize("now_time, expected_next, expected_last", [
        # Server updates at 00:00, 12:00, 18:00
        # Scenario 1: 02:30
        (datetime(2026, 5, 10, 2, 30), datetime(2026, 5, 10, 12, 0), datetime(2026, 5, 10, 0, 0)),
        # Scenario 2: 14:30
        (datetime(2026, 5, 10, 14, 30), datetime(2026, 5, 10, 18, 0), datetime(2026, 5, 10, 12, 0)),
        # Scenario 3: 21:30
        (datetime(2026, 5, 10, 21, 30), datetime(2026, 5, 11, 0, 0), datetime(2026, 5, 10, 18, 0)),
    ])
    def test_multiple_daily_updates(self, server, now_time, expected_next, expected_last):
        """
        Test multiple daily updates (00:00, 12:00, 18:00) at different times of the day.
        """
        now_time = now_time.replace(tzinfo=server.tz)
        expected_next = expected_next.replace(tzinfo=server.tz)
        expected_last = expected_last.replace(tzinfo=server.tz)

        updates = "00:00, 12:00, 18:00"
        with patch.object(ServerTime, 'now', return_value=now_time):
            assert to_utc(server.get_next_update(updates)) == to_utc(expected_next)
            assert to_utc(server.get_last_update(updates)) == to_utc(expected_last)

    @pytest.mark.parametrize("now_time, expected_next, expected_last", [
        # Server updates at 00:00 (Daily) and Mon 04:00 (Weekly)
        # In May 2026:
        # 1st is Friday
        # 4th is Monday
        # 11th, 18th, 25th are Mondays
        # 31st is Sunday

        # 1. May 1st 02:30 (Friday)
        # Next: May 2nd 00:00 (min of 2nd 00:00 and 4th 04:00)
        # Last: May 1st 00:00 (max of 1st 00:00 and Apr 27th 04:00)
        (datetime(2026, 5, 1, 2, 30), datetime(2026, 5, 2, 0, 0), datetime(2026, 5, 1, 0, 0)),

        # 2. May 1st 09:30 (Friday)
        # Next: May 2nd 00:00
        # Last: May 1st 00:00
        (datetime(2026, 5, 1, 9, 30), datetime(2026, 5, 2, 0, 0), datetime(2026, 5, 1, 0, 0)),

        # 3. May 25th 23:30 (Monday)
        # Next: May 26th 00:00 (min of 26th 00:00 and Jun 1st 04:00)
        # Last: May 25th 04:00 (max of 25th 00:00 and 25th 04:00)
        (datetime(2026, 5, 25, 23, 30), datetime(2026, 5, 26, 0, 0), datetime(2026, 5, 25, 4, 0)),

        # 4. May 26th 02:30 (Tuesday)
        # Next: May 27th 00:00 (min of 27th 00:00 and Jun 1st 04:00)
        # Last: May 26th 00:00 (max of 26th 00:00 and 25th 04:00)
        (datetime(2026, 5, 26, 2, 30), datetime(2026, 5, 27, 0, 0), datetime(2026, 5, 26, 0, 0)),

        # 5. May 31st 23:30 (Sunday)
        # Next: Jun 1st 00:00 (min of Jun 1st 00:00 and Jun 1st 04:00)
        # Last: May 31st 00:00 (max of May 31st 00:00 and May 25th 04:00)
        (datetime(2026, 5, 31, 23, 30), datetime(2026, 6, 1, 0, 0), datetime(2026, 5, 31, 0, 0)),
    ])
    def test_mixed_daily_weekly_updates(self, server, now_time, expected_next, expected_last):
        """
        Test mixed daily (00:00) and weekly (Mon 04:00) updates at specific boundary dates.
        """
        now_time = now_time.replace(tzinfo=server.tz)
        expected_next = expected_next.replace(tzinfo=server.tz)
        expected_last = expected_last.replace(tzinfo=server.tz)

        # weekday1 is Monday
        updates = ["00:00", "weekday1-04:00"]
        with patch.object(ServerTime, 'now', return_value=now_time):
            assert to_utc(server.get_next_update(updates)) == to_utc(expected_next)
            assert to_utc(server.get_last_update(updates)) == to_utc(expected_last)


class _FakeLocalTz(tzinfo):
    """
    Fake local timezone with real European DST rules (CET/CEST, UTC+1/+2).

    DST starts at 01:00 UTC on the last Sunday of March and ends at
    01:00 UTC on the last Sunday of October.
    """

    def utcoffset(self, dt):
        if dt is None:
            return None
        return timedelta(hours=2) if self._in_dst(dt) else timedelta(hours=1)

    def dst(self, dt):
        if dt is None:
            return None
        return timedelta(hours=1) if self._in_dst(dt) else timedelta(hours=0)

    def tzname(self, dt):
        if dt is None:
            return 'FAKE'
        return 'FAKEDST' if self._in_dst(dt) else 'FAKESTD'

    def fromutc(self, dt):
        """
        Convert a naive UTC datetime to local time, honoring the DST rules.

        Args:
            dt (datetime): Naive UTC datetime with tzinfo=self

        Returns:
            datetime: Local datetime with tzinfo=self
        """
        if dt.tzinfo is not self:
            raise ValueError('fromutc: dt.tzinfo is not self')
        year = dt.year
        start = self._last_sunday(year, 3).replace(hour=1)
        end = self._last_sunday(year, 10).replace(hour=1)
        utc = dt.replace(tzinfo=None)
        if start <= utc < end:
            return (dt + timedelta(hours=2)).replace(tzinfo=self)
        if end <= utc < end + timedelta(hours=1):
            # Repeated hour after fall-back: the second occurrence is standard time
            return (dt + timedelta(hours=1)).replace(tzinfo=self, fold=1)
        return (dt + timedelta(hours=1)).replace(tzinfo=self)

    @staticmethod
    def _last_sunday(year, month):
        """
        Get the last Sunday of a month.

        Args:
            year (int): Year
            month (int): Month

        Returns:
            datetime: Last Sunday of the month at 00:00
        """
        last_day = calendar.monthrange(year, month)[1]
        d = datetime(year, month, last_day)
        return d - timedelta(days=(d.weekday() + 1) % 7)

    def _in_dst(self, dt):
        """
        Check whether a local time is in DST.

        Args:
            dt (datetime): Local time with tzinfo=self

        Returns:
            bool: True if DST applies
        """
        if dt.fold:
            # Second occurrence of the repeated hour after fall-back
            return False
        year = dt.year
        start = self._last_sunday(year, 3).replace(hour=1)
        end = self._last_sunday(year, 10).replace(hour=1)
        utc_dst = dt.replace(tzinfo=None) - timedelta(hours=2)
        return start <= utc_dst < end


FAKE_LOCAL_TZ = _FakeLocalTz()


class _FakeLocalDatetime(datetime):
    """
    datetime subclass whose parameterless astimezone() converts to the fake
    DST local timezone instead of the system local timezone.
    """

    def astimezone(self, tz=None):
        if tz is None:
            tz = FAKE_LOCAL_TZ
        return super().astimezone(tz)


class TestServerTimeLocalDst:
    """
    Tests for local DST (daylight saving time) handling in ServerTime.

    ServerTime performs all arithmetic in the fixed-offset server timezone and
    only converts to the local timezone in the final astimezone() call. The
    host timezone cannot be controlled from a test, so the module's datetime
    is replaced with a subclass whose parameterless astimezone() converts to a
    fake local timezone with real European DST rules (UTC+1 winter, UTC+2
    summer). This makes DST behaviour deterministic on any host, including
    hosts without DST (e.g. UTC+8).
    """

    @pytest.fixture
    def dst_local_datetime(self, monkeypatch):
        """
        Replace servertime.datetime so parameterless astimezone() calls
        convert to the fake DST local timezone.
        """
        monkeypatch.setattr(servertime, 'datetime', _FakeLocalDatetime)

    def test_server_offset_fixed_across_seasons(self):
        """
        Server-side time is a fixed offset; it must not follow the local
        season, so all calculations stay on a continuous timeline.
        """
        st = ServerTime(8)
        winter = datetime(2026, 1, 15, 12, 0, tzinfo=st.tz)
        summer = datetime(2026, 7, 15, 12, 0, tzinfo=st.tz)
        assert winter.utcoffset() == summer.utcoffset() == timedelta(hours=8)

    def test_local_conversion_offsets_by_season(self, dst_local_datetime):
        """
        The same server moment maps to different local offsets in winter
        (UTC+1) and summer (UTC+2).
        """
        st = ServerTime(8)
        # server 12:00 +08 = 04:00 UTC
        winter = servertime.datetime(2026, 1, 15, 12, 0, tzinfo=st.tz).astimezone()
        summer = servertime.datetime(2026, 7, 15, 12, 0, tzinfo=st.tz).astimezone()
        assert winter.utcoffset() == timedelta(hours=1)
        assert winter.hour == 5
        assert summer.utcoffset() == timedelta(hours=2)
        assert summer.hour == 6

    def test_get_next_update_winter(self, dst_local_datetime):
        """Daily update converted to local time in winter (CET, UTC+1)."""
        st = ServerTime(8)
        now = servertime.datetime(2026, 1, 15, 20, 0, tzinfo=st.tz)
        with patch.object(ServerTime, 'now', return_value=now):
            result = st.get_next_update("04:00")
        # server 2026-01-16 04:00 +08 = 2026-01-15 20:00 UTC -> local 21:00 +1
        assert to_utc(result) == datetime(2026, 1, 15, 20, 0, tzinfo=timezone.utc)
        assert result.utcoffset() == timedelta(hours=1)
        assert result.hour == 21

    def test_get_next_update_summer(self, dst_local_datetime):
        """Daily update converted to local time in summer (CEST, UTC+2)."""
        st = ServerTime(8)
        now = servertime.datetime(2026, 7, 15, 20, 0, tzinfo=st.tz)
        with patch.object(ServerTime, 'now', return_value=now):
            result = st.get_next_update("04:00")
        # server 2026-07-16 04:00 +08 = 2026-07-15 20:00 UTC -> local 22:00 +2
        assert to_utc(result) == datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc)
        assert result.utcoffset() == timedelta(hours=2)
        assert result.hour == 22

    def test_get_next_update_monthday_in_summer(self, dst_local_datetime):
        """Monthly update (monthday branch constructs new datetimes) also
        converts to the DST local timezone."""
        st = ServerTime(8)
        now = servertime.datetime(2026, 8, 15, 20, 0, tzinfo=st.tz)
        with patch.object(ServerTime, 'now', return_value=now):
            result = st.get_next_update("monthday31-04:00")
        # server 2026-08-31 04:00 +08 = 2026-08-30 20:00 UTC -> local 22:00 +2
        assert to_utc(result) == datetime(2026, 8, 30, 20, 0, tzinfo=timezone.utc)
        assert result.utcoffset() == timedelta(hours=2)
        assert result.hour == 22

    def test_get_next_update_spring_forward(self, dst_local_datetime):
        """
        On spring-forward day (2026-03-29 01:00 UTC, CET -> CEST) the local
        hour 02:00-02:59 does not exist; the update lands at 03:00 +2.
        """
        st = ServerTime(8)
        now = servertime.datetime(2026, 3, 29, 8, 0, tzinfo=st.tz)  # 00:00 UTC
        with patch.object(ServerTime, 'now', return_value=now):
            result = st.get_next_update("09:00")
        # server 09:00 +08 = 01:00 UTC -> local jumps to 03:00 +2
        assert to_utc(result) == datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc)
        assert result.utcoffset() == timedelta(hours=2)
        assert result.hour == 3

    def test_get_next_update_fall_back(self, dst_local_datetime):
        """
        On fall-back day (2026-10-25 01:00 UTC, CEST -> CET) the local hour
        02:00-02:59 occurs twice; the update resolves to the second occurrence
        (fold=1) with the standard offset +1.
        """
        st = ServerTime(8)
        now = servertime.datetime(2026, 10, 25, 8, 0, tzinfo=st.tz)  # 00:00 UTC
        with patch.object(ServerTime, 'now', return_value=now):
            result = st.get_next_update("09:00")
        # server 09:00 +08 = 01:00 UTC -> local 02:00 +1 (second occurrence)
        assert to_utc(result) == datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)
        assert result.utcoffset() == timedelta(hours=1)
        assert result.hour == 2
        assert result.fold == 1

    def test_get_last_update_around_fall_back(self, dst_local_datetime):
        """
        The last update before/after the fall-back boundary keeps the correct
        local offset on both sides of the transition.
        """
        st = ServerTime(8)

        # On the fall-back day, the last 04:00 (+08) update is still in DST
        now = servertime.datetime(2026, 10, 25, 20, 0, tzinfo=st.tz)
        with patch.object(ServerTime, 'now', return_value=now):
            result = st.get_last_update("04:00")
        # server 2026-10-25 04:00 +08 = 2026-10-24 20:00 UTC -> local 22:00 +2
        assert to_utc(result) == datetime(2026, 10, 24, 20, 0, tzinfo=timezone.utc)
        assert result.utcoffset() == timedelta(hours=2)
        assert result.hour == 22

        # After the fall-back, the last 04:00 (+08) update is in standard time
        now = servertime.datetime(2026, 10, 26, 20, 0, tzinfo=st.tz)
        with patch.object(ServerTime, 'now', return_value=now):
            result = st.get_last_update("04:00")
        # server 2026-10-26 04:00 +08 = 2026-10-25 20:00 UTC -> local 21:00 +1
        assert to_utc(result) == datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)
        assert result.utcoffset() == timedelta(hours=1)
        assert result.hour == 21

    def test_delta_to_update_unaffected_by_local_dst(self, dst_local_datetime):
        """
        get_delta_to_update() works entirely in the server timezone, so the
        local DST must not change the result across seasons.
        """
        st = ServerTime(8)
        winter_now = servertime.datetime(2026, 1, 15, 20, 0, tzinfo=st.tz)
        summer_now = servertime.datetime(2026, 7, 15, 20, 0, tzinfo=st.tz)
        with patch.object(ServerTime, 'now', return_value=winter_now):
            winter_delta = st.get_delta_to_update("04:00")
        with patch.object(ServerTime, 'now', return_value=summer_now):
            summer_delta = st.get_delta_to_update("04:00")
        assert winter_delta == summer_delta == timedelta(hours=8)

    def test_get_next_update_uses_system_local_timezone(self):
        """
        Without the fake patch, get_next_update() converts to the real system
        local timezone (whatever it is on the host).
        """
        st = ServerTime(8)
        result = st.get_next_update("04:00")
        assert result.tzinfo is not None
        assert result.utcoffset() == datetime.now().astimezone().utcoffset()


class TestRandomTime:
    """Tests for random_time()."""

    @pytest.mark.parametrize("second, expected", [
        (3, 3.0),
        (0, 0.0),
        (5.5, 5.5),
        (0.5, 0.5),
        ("3", 3.0),
        ("0.5", 0.5),
    ])
    def test_single_value(self, second, expected):
        """Single value returns that value as float."""
        assert random_time(second) == expected
        assert isinstance(random_time(second), float)

    @pytest.mark.parametrize("second, low, high", [
        ((1, 4), 1.0, 4.0),
        ((1.5, 2.5), 1.5, 2.5),
        ([0, 3], 0.0, 3.0),
        ([0.5, 1.5], 0.5, 1.5),
        ("0.1~0.2", 0.1, 0.2),
        ("1.5, 2.5", 1.5, 2.5),
        ("10-30", 10.0, 30.0),
        ("0, 1", 0.0, 1.0),
    ])
    def test_range_bounds(self, second, low, high):
        """Range value returns float within [low, high]."""
        for _ in range(100):
            result = random_time(second)
            assert isinstance(result, float)
            assert low <= result <= high, f"Expected [{low}, {high}] for {second!r}, got {result}"

    def test_float_range_produces_fractional_values(self):
        """
        Float range input produces values with sub-second precision,
        not just whole integers.
        """
        results = {random_time((0.5, 1.5)) for _ in range(200)}
        assert any(v != int(v) for v in results), (
            f"All values were whole numbers: {sorted(results)}"
        )

    def test_precision_three_millisecond_resolution(self):
        """
        With precision=3 (default), the step should be 10**3=1000,
        producing randomness at 0.001s granularity.
        """
        results = {random_time((0, 1), precision=3) for _ in range(500)}
        # Every value must be a multiple of 0.001
        for v in results:
            thousandths = round(v * 1000)
            assert abs(v - thousandths / 1000) < 1e-10, (
                f"Value {v} is not a multiple of 0.001"
            )
        # At least some values should have non-zero thousandths digit,
        # proving actual 0.001-level precision beyond just 0.01 steps
        has_ms = any(round(v * 1000) % 10 != 0 for v in results)
        assert has_ms, (
            f"All values were multiples of 0.01, expected some 0.001-level: "
            f"{sorted(results)}"
        )

    def test_round_prevents_floating_point_noise(self):
        """
        round(value, precision) must prevent floating-point artifacts
        like 0.300000001 from appearing.
        """
        for _ in range(500):
            v = random_time((0, 1), precision=3)
            assert v == round(v, 3), f"Floating-point noise detected: {v}"
