# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta, time
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig


class WantedQuestsConfig(BaseModel):
    before_end: Time = Field(default=Time(0, 0, 0), description='before_end_help')


class WantedQuests(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    wanted_quests_config: WantedQuestsConfig = Field(default_factory=WantedQuestsConfig)





