# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase


class DailyTriflesConfig(BaseModel):
    one_summon: bool = Field(title='One Summon', default=False)
    guild_wish: bool = Field(title='Guild Wish', default=False)
    friend_love: bool = Field(title='Friend Love', default=False)
    luck_msg: bool = Field(title='Luck Msg', default=False)
    store_sign: bool = Field(title='Store Sign', default=False, description='store_sign_help')


class DailyTrifles(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    trifles_config: DailyTriflesConfig = Field(default_factory=DailyTriflesConfig)

