# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta, datetime, time
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time

class ShopConfig(BaseModel):
    time_of_mystery: Time = Field(default=Time(hour=0, minute=0, second=0), description='time_of_mystery_help')
    mystery_amulet: bool = Field(default=False)
    black_daruma_scrap: bool = Field(default=False)
    shop_kaiko_3: bool = Field(default=False)
    shop_kaiko_4: bool = Field(default=False)




class ShareConfig(BaseModel):
    enable: bool = Field(default=False)
    share_friend_1: str = Field(title='Share Friend 1', default='', description='share_friend_1_help')
    share_friend_2: str = Field(title='Share Friend 2', default='')
    share_friend_3: str = Field(title='Share Friend 3', default='')
    share_friend_4: str = Field(title='Share Friend 4', default='')
    share_friend_5: str = Field(title='Share Friend 5', default='')

class MysteryShop(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    shop_config: ShopConfig = Field(default_factory=ShopConfig)
    share_config: ShareConfig = Field(default_factory=ShareConfig)

