# This Python file uses the following encoding: utf-8
"""防风控作息看守器: 睡眠窗 / 每日活跃上限 / 强制长休息, 由 Script 持有。"""
from datetime import datetime, timedelta


class AntiBanGuard:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._active_date = None
        self._active_seconds_today = 0.0
        self._rest_until = None

    @staticmethod
    def _in_sleep_window(t, start, end) -> bool:
        if start == end:
            return False
        if start < end:
            return start <= t < end
        return t >= start or t < end

    @staticmethod
    def _next_time_point(now: datetime, end) -> datetime:
        candidate = now.replace(hour=end.hour, minute=end.minute, second=end.second, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    def _roll_day(self, today) -> None:
        if self._active_date != today:
            self._active_date = today
            self._active_seconds_today = 0.0

    def record_active(self, seconds: float) -> None:
        self._roll_day(datetime.now().date())
        self._active_seconds_today += seconds

    def wake_time(self, now: datetime, config):
        if not config.enable:
            return None
        wake = None
        if self._in_sleep_window(now.time(), config.sleep_start, config.sleep_end):
            wake = self._next_time_point(now, config.sleep_end)
        limit = config.daily_active_limit.total_seconds()
        if limit > 0:
            self._roll_day(now.date())
            if self._rest_until and now < self._rest_until:
                wake = max(wake, self._rest_until) if wake else self._rest_until
            elif self._active_seconds_today >= limit:
                self._rest_until = now + config.long_rest_duration
                self._active_seconds_today = 0.0
                wake = max(wake, self._rest_until) if wake else self._rest_until
        return wake
