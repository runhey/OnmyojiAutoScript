# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig

class ExperienceYoukaiConfig(ConfigBase):
    buff_exp_50_click: bool = Field(default=False)
    buff_exp_100_click: bool = Field(default=False)

class ExperienceYoukai(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    experience_youkai: ExperienceYoukaiConfig = Field(default_factory=ExperienceYoukaiConfig)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
