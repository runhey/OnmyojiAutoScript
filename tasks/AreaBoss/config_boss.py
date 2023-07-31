# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field

class Boss(BaseModel):
    boss_number: int = Field(title='Boss Number',
                             default=3,
                             description='默认为3 可选[1-3], 当你设置为三时默认你拥有全部的挑战资格，会挑战热门的前三个，\n'
                                         '如果不是请将你可以挑战的boss进行收藏',
                             ge=1, le=3)
