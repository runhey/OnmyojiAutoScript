# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig

class GoldYoukaiConfig(ConfigBase):
    buff_gold_50_click: bool = Field(default=False)
    buff_gold_100_click: bool = Field(default=False)

class GoldYoukai(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    gold_youkai: GoldYoukaiConfig = Field(default_factory=GoldYoukaiConfig)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)

