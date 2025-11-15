# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum

from datetime import timedelta
from pydantic import BaseModel, Field, validator

from tasks.Component.config_base import MultiLine
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, TimeDelta
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig


class MC(str, Enum):
    AW1 = '觉醒一'
    AW2 = '觉醒二'
    AW3 = '觉醒三'
    GR1 = '御灵一'
    GR2 = '御灵二'
    GR3 = '御灵三'
    SO1 = '御魂一'
    SO2 = '御魂二'
    FEED = '养成'  # 喂N卡


class MissionsConfig(BaseModel):
    missions_select: MC = Field(default=MC.AW1, description='选择远远不够对应的任务')


class CollectiveMissions(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    missions_config: MissionsConfig = Field(default_factory=MissionsConfig)


if __name__ == '__main__':
    print(MC('觉醒一'))
