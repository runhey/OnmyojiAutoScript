# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig

class TakoConfig(BaseModel):
    enable: bool = Field(default=False)
    buff_gold_50_click: bool = Field(default=False)
    buff_gold_100_click: bool = Field(default=False)
    buff_exp_50_click: bool = Field(default=False)
    buff_exp_100_click: bool = Field(default=False)


class TakoTime(ConfigBase):
    # 自定义运行时间（每天按 first_time、second_time 各运行一次）
    first_time: Time = Field(default=Time(hour=10, minute=0, second=0))
    second_time: Time = Field(default=Time(hour=13, minute=0, second=0))


class Tako(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    tako_time: TakoTime = Field(default_factory=TakoTime)
    tako_config: TakoConfig = Field(default_factory=TakoConfig)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)