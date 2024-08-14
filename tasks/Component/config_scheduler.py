# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
from enum import Enum
from datetime import datetime, timedelta, time
from pydantic import BaseModel, ValidationError, validator, Field

from tasks.Component.config_base import ConfigBase, TimeDelta, DateTime, Time

class Scheduler(ConfigBase):
    enable: bool = Field(default=False, description='enable_help')
    next_run: DateTime = Field(default="2023-01-01 00:00:00", description='next_run_help')
    priority: int = Field(default=5, description='priority_help')

    success_interval: TimeDelta = Field(default=TimeDelta(days=1), description='success_interval_help')
    failure_interval: TimeDelta = Field(default=TimeDelta(days=1), description='failure_interval_help')
    server_update: Time = Field(default=Time(hour=9, minute=0, second=0), description='server_update_help')
    float_time: Time = Field(default=Time(hour=0, minute=0, second=0), description='下次运行时间将在此范围内随机浮动。未设强制执行时，推荐浮动小于间隔：如寮突30±5分钟，寄养6±0.2小时；有强制执行时，确保不超出窗口：如麒麟19:01±1分钟，逢魔18:00±0.5小时，避免影响其他任务')

    @validator('next_run', pre=True, always=True)
    def parse_next_run(cls, value):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise ValueError('Invalid next_run value. Expected format: YYYY-MM-DD HH:MM:SS')
        return value

    @validator('success_interval', 'failure_interval', pre=True)
    def parse_interval(cls, value):
        if isinstance(value, str):
            try:
                pattern = r'(\d{1,2})\s+(\d{1,2}):(\d{1,2}):(\d{1,2})'
                match = re.match(pattern, value)
                if match:
                    days = int(match.group(1))
                    hours = int(match.group(2))
                    minutes = int(match.group(3))
                    seconds = int(match.group(4))
                    return TimeDelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
                return TimeDelta(days=1, hours=0, minutes=0, seconds=0)
            except ValueError:
                raise ValueError('Invalid interval value. Expected format: seconds')
        return value


if __name__ == "__main__":
    s = Scheduler(success_interval='00 00:00:10')
    if isinstance(s.success_interval, TimeDelta):
        print(s.success_interval.seconds)
    print(s.json())
    print(s.dict())


