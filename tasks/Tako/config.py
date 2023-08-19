# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig

class TakoConfig(BaseModel):
    enable: bool = Field(default=False)
    buff_gold_50_click: bool = Field(default=False)
    buff_gold_100_click: bool = Field(default=False)
    buff_exp_50_click: bool = Field(default=False)
    buff_exp_100_click: bool = Field(default=False)


class Tako(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    tako_config: TakoConfig = Field(default_factory=TakoConfig)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)