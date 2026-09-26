"""
Test that PatchTime correctly mocks datetime when using
``from datetime import datetime`` at module level — the same import
style used by ``alasio/base/servertime.py`` and other project modules.
"""
from datetime import date, datetime, timedelta, timezone

from oas.testing.patch_time import PatchTime


class TestDirectImportMocked:
    """Inside PatchTime, ``from datetime import datetime`` returns mocked time."""

    def test_now_no_tz(self):
        with PatchTime(1234567890.0):
            now = datetime.now()
            expected = datetime.fromtimestamp(1234567890.0)
            assert now == expected

    def test_now_with_tz_utc(self):
        with PatchTime(1234567890.0):
            now = datetime.now(tz=timezone.utc)
            assert now.tzinfo is not None
            assert now.timestamp() == 1234567890.0

    def test_now_with_tz_non_utc(self):
        tz = timezone(timedelta(hours=8))
        with PatchTime(1234567890.0):
            now = datetime.now(tz=tz)
            assert now.tzinfo is not None
            expected = datetime.fromtimestamp(1234567890.0, tz=timezone.utc).astimezone(tz)
            assert now == expected

    def test_utcnow(self):
        with PatchTime(1234567890.0):
            utcnow = datetime.utcnow()
            expected = datetime(2009, 2, 13, 23, 31, 30)
            assert utcnow == expected

    def test_today(self):
        with PatchTime(1234567890.0):
            today = datetime.today()
            expected = datetime.fromtimestamp(1234567890.0)
            assert today == expected

    def test_date_today(self):
        with PatchTime(1234567890.0):
            today = date.today()
            expected = datetime.fromtimestamp(1234567890.0).date()
            assert today == expected


class TestDirectImportRestore:
    """After PatchTime exits, ``from datetime import datetime`` returns real time."""

    def test_exit_restores_now_utc(self):
        with PatchTime(1234567890.0):
            assert datetime.now(tz=timezone.utc).timestamp() == 1234567890.0
        import time
        real = datetime.now(tz=timezone.utc).timestamp()
        assert abs(real - time.time()) < 1.0

    def test_exit_restores_utcnow(self):
        with PatchTime(1234567890.0):
            assert datetime.utcnow().hour == 23  # 2009-02-13 23:31:30
        real = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        import time
        assert abs((real - datetime(1970, 1, 1)).total_seconds() - time.time()) < 1.0
