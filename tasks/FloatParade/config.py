# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta
from enum import Enum
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler as BaseScheduler
from tasks.Component.config_base import ConfigBase, TimeDelta

class Scheduler(BaseScheduler):
    success_interval: TimeDelta = Field(default=TimeDelta(days=3), description='success_interval_help')
    failure_interval: TimeDelta = Field(default=TimeDelta(days=3), description='failure_interval_help')

class LevelReward(str, Enum):
    ONE = '蛇皮/青吉鬼'
    TWO = '金币/勾玉'
    THREE = '体力/樱饼'

class FloatParadeConfig(BaseModel):
    level_reward: LevelReward = Field(default=LevelReward.TWO)

class FloatParade(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    float_parade: FloatParadeConfig = Field(default_factory=FloatParadeConfig)