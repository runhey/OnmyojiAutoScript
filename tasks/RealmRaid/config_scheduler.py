# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, timedelta
from pydantic import BaseModel, ValidationError, validator, Field

class Scheduler(BaseModel):
    enable: bool = Field(default=False, description='[是否启用]:默认为False')
    next_run: datetime = Field(default="2023-01-01 00:00:00", description='[下次执行时间]:默认为2023-01-01 00:00:00\n 清空后回车设置当前的时间')
    interval_days: int = Field(default=1, description='[间隔天数]:默认为1\n 可选0-7')
    interval_hours: int = Field(default=0, description='[间隔小时]:默认为0\n 可选0-23')
    interval_minutes: int = Field(default=0, description='[间隔分钟]:默认为0\n 可选0-59')

