# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from tasks.Component.config_base import ConfigBase, TimeDelta, DateTime, Time
from pydantic import BaseModel, ValidationError, validator, Field
from enum import Enum

# 鬼王的难度为： 易、中、高、难、极 五个 对应英文：easy、medium、hard、difficult、extreme

class Scheduler(ConfigBase):
    enable: bool = Field(default=False, description='enable_help')
    next_run: DateTime = Field(default="2023-01-01 00:00:00", description='next_run_help')
    priority: int = Field(default=5, description='priority_help')
    interval: TimeDelta = Field(default=TimeDelta(hours=3), description='interval_help')

class MetaDemonConfig(ConfigBase):
    auto_tea: bool = Field(default=False, description='auto_tea_help')
    extreme_notify: bool = Field(default=False, description='extreme_notify_help')


class MetaDemon(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    meta_demon_config: MetaDemonConfig = Field(default_factory=MetaDemonConfig)




