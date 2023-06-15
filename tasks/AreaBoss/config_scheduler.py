# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field

class Scheduler(BaseModel):
    enable: bool = Field(default=False,
                         description='none')
    next_run: datetime = Field(default="2023-01-01 00:00:00",
                               description='none')
    priority: int = Field(default=3,
                          description='已经弃置，不生效')

