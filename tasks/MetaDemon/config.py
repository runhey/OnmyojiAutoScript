# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from tasks.Component.config_base import ConfigBase, TimeDelta, DateTime, Time
from pydantic import BaseModel, ValidationError, validator, Field
from enum import Enum
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig

# 鬼王的难度为： 易、中、高、难、极 五个 对应英文：easy、medium、hard、difficult、extreme


class MetaDemonConfig(ConfigBase):
    auto_tea: bool = Field(default=False, description='auto_tea_help')
    extreme_notify: bool = Field(default=False, description='extreme_notify_help')


class MetaDemon(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    meta_demon_config: MetaDemonConfig = Field(default_factory=MetaDemonConfig)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)




