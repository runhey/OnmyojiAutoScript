# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field

from module.logger import logger

class Scheduler(BaseModel):
    enable: bool = Field(default=False,
                         description='none')
    next_run: datetime = Field(default="2023-01-01 00:00:00",
                               description='none')
    priority: int = Field(default=0,
                          description='default 0')
    command: str = Field(default='Restart',
                         description='none')
    success_interval: float = Field(default=0,
                                    description='none')
    failure_interval: float = Field(default=0,
                                    description='none')
    server_update: time = Field(default="00:00",
                                description='none')
