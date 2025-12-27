# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time


class SixRealmsGate(BaseModel):
    number_enable: bool = Field(default=False, description='只打门票')
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    # 限制次数
    limit_count: int = Field(default=1, description='limit_count_help')


class SwitchSoulConfig(BaseModel):
    enable: bool = Field(default=False, description='auto_enable_help')
    # 换第一行
    one_switch: str = Field(default='-1,-1', description='换第一行')
    # 换第二行
    two_switch: str = Field(default='-1,-1', description='换第二行')


class SixRealms(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    six_realms_gate: SixRealmsGate = Field(default_factory=SixRealmsGate)













