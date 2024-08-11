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

class WhenAttackFail(str, Enum):
    EXIT: str = 'Exit'
    CONTINUE: str = 'Continue'
    REFRESH: str = 'Refresh'

class RaidConfig(BaseModel):
    # raid_mode: RaidMode = Field(title='Raid Mode', default=RaidMode.NORMAL,
    #                             description='raid_mode_help')
    # attack_number: AttackNumber = Field(title='Attack Number', default=AttackNumber.ALL,
    #                                     description='')

    number_attack: int = Field(title='Number Attack', default=30, le=30, ge=1, description='number_attack_help')
    number_base: int = Field(title='Number Base', default=0, le=20, ge=0, description='number_base_help')
    exit_four: bool = Field(title='Exit Four', default=True, description='exit_four_help')
    order_attack: str = Field(title='Order Attack', default='5 > 4 > 3 > 2 > 1 > 0', description='order_attack_help')
    three_refresh: bool = Field(title='Three Refresh', default=False, description='three_refresh_help')
    when_attack_fail: WhenAttackFail = Field(title='WhenAttackFail', default=WhenAttackFail.REFRESH, description='when_attack_fail_help')

class RealmRaid(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    raid_config: RaidConfig = Field(default_factory=RaidConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)







