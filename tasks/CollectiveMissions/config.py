# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta
from pydantic import BaseModel, Field

from tasks.Component.config_base import MultiLine
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, TimeDelta
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig



class MissionsConfig(BaseModel):
    # 契灵 > 觉醒二 > 觉醒一 > 御灵二 > 御灵一 > 御魂五 > 御魂四
    missions_rule: MultiLine = Field(default='契灵 > 觉醒三 > 觉醒二 > 觉醒一 > 御灵二 > 御灵一 > 御魂五 > 御魂四',
                                     description='missions_rule_help')


class CollectiveMissions(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    missions_config: MissionsConfig = Field(default_factory=MissionsConfig)





