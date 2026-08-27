# This Python file uses the following encoding: utf-8
# @author runhey
from datetime import timedelta
from pydantic import BaseModel, Field

from tasks.Component.config_base import Time, TimeDelta


class AntiBan(BaseModel):
    enable: bool = Field(default=False, description='antiban_enable_help')
    sleep_start: Time = Field(default=Time(hour=2, minute=0, second=0),
                              description='sleep_start_help')
    sleep_end: Time = Field(default=Time(hour=8, minute=0, second=0),
                            description='sleep_end_help')
    daily_active_limit: TimeDelta = Field(default=timedelta(hours=0),
                                          description='daily_active_limit_help')
    long_rest_duration: TimeDelta = Field(default=timedelta(hours=2),
                                          description='long_rest_duration_help')
