# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase


class DanceConfig(BaseModel):
    one_summon: bool = Field(title='One Summon', default=False)
    guild_wish: bool = Field(title='Guild Wish', default=False)
    friend_love: bool = Field(title='Friend Love', default=False)
    store_sign: bool = Field(title='Store Sign', default=False, description='store_sign_help')


class DanceTril(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)

