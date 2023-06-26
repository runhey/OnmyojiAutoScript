# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, timedelta
from pydantic import BaseModel, ValidationError, validator, Field

class Scheduler(BaseModel):
    enable: bool = Field(default=False, description='enable_help')
    next_run: datetime = Field(default="2023-01-01 00:00:00", description='next_run_help')
    priority: int = Field(default=5, description='priority_help')
    interval_days: int = Field(default=1, description='interval_days_help')
    interval_hours: int = Field(default=0, description='interval_hours_help')
    interval_minutes: int = Field(default=0, description='interval_minutes_help')

    @validator('next_run', pre=True, always=True)
    def parse_next_run(cls, value):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise ValueError('Invalid next_run value. Expected format: YYYY-MM-DD HH:MM:SS')
        return value

