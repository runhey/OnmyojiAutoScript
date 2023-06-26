# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig


class RaidMode(str, Enum):
    NORMAL = 'retreat_four_attack_nine'
    ATTACK_ALL = 'attack_all'

class AttackNumber(str, Enum):
    NINE = 'nine'
    ALL = 'all'

class RaidConfig(BaseModel):
    raid_mode: RaidMode = Field(title='Raid Mode', default=RaidMode.NORMAL,
                                description='[挑战模式]:默认为退四打九\n 退四打九指每次执行前都会退出四次，然后在进攻九次')
    attack_number: AttackNumber = Field(title='Attack Number', default=AttackNumber.ALL,
                                        description='[挑战次数]:默认为all，一直打到没有\n nine为打九次')

class RealmRaid(BaseModel):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    raid_config: RaidConfig = Field(default_factory=RaidConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)







