# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field

class Boss(BaseModel):
    boss_number: int = Field(title='Boss Number',
                             default=3,
                             description='只可选范围1~3',
                             ge=1, le=3)
