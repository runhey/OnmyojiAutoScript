# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig


class SougenbiClass(str, Enum):
    GREED = '贪'
    Anger = '嗔'
    Foolery = '痴'

class SougenbiConfig(ConfigBase):
    sougenbi_class: SougenbiClass = Field(default=SougenbiClass.Foolery)
    # 限制时间
    limit_time: time = Field(default=time(minute=30), description='limit_time_help')
    # 限制次数
    limit_count: int = Field(default=30, description='limit_count_help')


class Sougenbi(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    sougenbi_config: SougenbiConfig = Field(default_factory=SougenbiConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)

