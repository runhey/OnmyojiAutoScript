# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field

class InviteNumber(str, Enum):
    ONE = 'one'
    TWO = 'two'

class FindMode(str, Enum):
    AUTO_FIND = 'auto_find'
    RECENT_FRIEND = 'recent_friend'

class InviteConfig(BaseModel):

    invite_number: InviteNumber = Field(default=InviteNumber.ONE, description='invite_number_help')
    friend_1: str = Field(default='', description='friend_name_help')
    friend_2: str = Field(default='', description='friend_2_name_help')
    find_mode: FindMode = Field(default=FindMode.AUTO_FIND, description='find_mode_help')
    wait_time: time = Field(default=time(minute=1), description='wait_time_help')

    # recent_friend, guild_friend, friend, other_friend

