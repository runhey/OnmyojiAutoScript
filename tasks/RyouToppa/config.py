from pydantic import BaseModel, Field
from enum import Enum
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler


class RaidMode(str, Enum):
    ATTACK_ALL = 'attack_all'


class AttackNumber(str, Enum):
    ALL = 'all'


class HaveManageAccess(str, Enum):
    YES = 'yes'
    NO = 'no'


class RaidConfig(BaseModel):
    raid_mode: RaidMode = Field(title='Raid Mode', default=RaidMode.ATTACK_ALL,
                                description='raid_mode_help')
    attack_number: AttackNumber = Field(title='Attack Number', default=AttackNumber.ALL,
                                        description='')
    ryou_access: HaveManageAccess = Field(title='Ryou Access', default=HaveManageAccess.YES,
                                          description='是否是寮管理')


class RyouToppa(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    raid_config: RaidConfig = Field(default_factory=RaidConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)