# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field

from module.logger import logger

class Scheduler(BaseModel):
    enable: bool = Field(default=True, description='none')
    next_run: datetime = Field(default="2023-01-01 00:00:00", description='无需手动修改')
    priority: int = Field(default=0, description='重启的优先级最高，数值为0，保持默认即可')

    success_interval: float = Field(default=0,
                                    description='none')
    failure_interval: float = Field(default=0,
                                    description='none')
    server_update: time = Field(default="00:00", description='none')

    @validator('next_run', pre=True, always=True)
    def parse_next_run(cls, value):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise ValueError('Invalid next_run value. Expected format: YYYY-MM-DD HH:MM:SS')
        return value
