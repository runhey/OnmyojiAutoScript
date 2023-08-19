# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, TimeDelta
from tasks.Utils.config_enum import ShikigamiClass

class GreenMarkType(str, Enum):
    LEFT_1 = 'left_1'
    LEFT_2 = 'left_2'
    LEFT_3 = 'left_3'
    LEFT_4 = 'left_4'
    LEFT_5 = 'left_5'
    LEFT_6 = 'left_6'
    MAIN = 'main'



class TrueOrochiScheduler(Scheduler):
    priority = Field(default=10, description='priority_help')
    success_interval: TimeDelta = Field(default=TimeDelta(days=7), description='success_interval_help')
    failure_interval: TimeDelta = Field(default=TimeDelta(days=1), description='failure_interval_help')

class TrueOrochiConfig(BaseModel):
    find_true_orochi: bool = Field(default=True, description='find_true_orochi_help')
    # green_enable: bool = Field(default=False, description='green_enable_help')
    # green_mark_type: GreenMarkType = Field(default=GreenMarkType.LEFT_1, description='green_mark_type_help')
    current_success: int = Field(default=0, description='current_success_help')

class TrueOrochi(ConfigBase):
    scheduler: TrueOrochiScheduler = Field(default_factory=TrueOrochiScheduler)
    true_orochi_config: TrueOrochiConfig = Field(default_factory=TrueOrochiConfig)

