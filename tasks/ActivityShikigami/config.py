# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import time, timedelta
from pydantic import BaseModel, Field

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, TimeDelta
from tasks.Component.BaseActivity.config_activity import GeneralClimb

class ShikigamiConfig(BaseModel):
    limit_time: TimeDelta = Field(default=TimeDelta(hours=0, minutes=30, seconds=0), description='limit_time_help')
    limit_count: int = Field(default=10, description='limit_count_help')


class ActivityShikigami(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    # shikigami: ShikigamiConfig = Field(default_factory=ShikigamiConfig)
    general_climb: GeneralClimb = Field(default_factory=GeneralClimb)
    general_battle: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)




