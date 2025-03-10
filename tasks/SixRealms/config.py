# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig


class SixRealmsGate(BaseModel):
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    # 限制次数
    limit_count: int = Field(default=1, description='limit_count_help')


class SixRealms(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    switch_soul_config_1: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    switch_soul_config_2: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    six_realms_gate: SixRealmsGate = Field(default_factory=SixRealmsGate)













