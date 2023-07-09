# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, TimeDelta
from tasks.Utils.config_enum import ShikigamiClass

class UtilizeScheduler(Scheduler):
    priority = Field(default=2, description='priority_help')
    success_interval: TimeDelta = Field(default=TimeDelta(hours=6), description='success_interval_help')
    failure_interval: TimeDelta = Field(default=TimeDelta(hours=6), description='failure_interval_help')

class UtilizeConfig(BaseModel):
    utilize_rule: str = Field(default='auto', description='utilize_rule_help')
    auto_switch_sort: bool = Field(default=True, description='auto_switch_sort_help')
    shikigami_class: ShikigamiClass = Field(default=ShikigamiClass.N, description='shikigami_class_help')
    shikigami_order: int = Field(default=4, description='shikigami_order_help')
    guild_ap_enable: bool = Field(default=True, description='guild_ap_enable_help')
    guild_assets_enable: bool = Field(default=True, description='guild_assets_enable_help')
    box_ap_enable: bool = Field(default=True, description='box_ap_enable_help')
    box_exp_enable: bool = Field(default=True, description='box_exp_enable_help')


class KekkaiUtilize(ConfigBase):
    scheduler: UtilizeScheduler = Field(default_factory=UtilizeScheduler)
    utilize_config: UtilizeConfig = Field(default_factory=UtilizeConfig)



