# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.config_base import ConfigBase
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig

class RaidMode(str, Enum):
    NORMAL = 'retreat_four_attack_nine'
    ATTACK_ALL = 'attack_all'

class AttackNumber(str, Enum):
    NINE = 'nine'
    ALL = 'all'

class RaidConfig(BaseModel):
    raid_mode: RaidMode = Field(title='Raid Mode', default=RaidMode.NORMAL,
                                description='raid_mode_help')
    attack_number: AttackNumber = Field(title='Attack Number', default=AttackNumber.ALL,
                                        description='')

class RealmRaid(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    raid_config: RaidConfig = Field(default_factory=RaidConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)







