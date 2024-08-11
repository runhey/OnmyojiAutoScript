# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler as BaseScheduler
from tasks.Component.config_base import ConfigBase, TimeDelta

class Scheduler(BaseScheduler):
    success_interval: TimeDelta = Field(default=TimeDelta(days=7), description='success_interval_help')
    failure_interval: TimeDelta = Field(default=TimeDelta(days=7), description='failure_interval_help')

class Trifles(BaseModel):
    share_collect: bool = Field(default=True, description='share_collect_help')
    share_area_boss: bool = Field(default=True, description='share_area_boss_help')
    share_secret: bool = Field(default=True, description='share_secret_help')
    broken_amulet: int = Field(title='Broken Amulet', default=100, description='trifles_broken_amulet_help')


class WeeklyTrifles(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    trifles: Trifles = Field(default_factory=Trifles)

