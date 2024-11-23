# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time

class HuntTime(ConfigBase):
    # 自定义运行时间
    kirin_time: Time = Field(default=Time(hour=19, minute=0, second=0))
    netherworld_time: Time = Field(default=Time(hour=19, minute=0, second=0))

class HuntConfig(BaseModel):
    kirin_group_team: str = Field(default='-1,-1', description='switch_group_team_help')
    netherworld_group_team: str = Field(default='-1,-1')


class Hunt(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    hunt_time: HuntTime = Field(default_factory=HuntTime)
    hunt_config: HuntConfig = Field(default_factory=HuntConfig)
