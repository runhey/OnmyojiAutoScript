from pydantic import BaseModel, Field
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler
from enum import Enum


class ExplorationMode(str, Enum):
    CAPTAIN = '队长'
    MEMBER = '队员'


class ExplorationConfig(BaseModel):
    mode: ExplorationMode = Field(title='探索模式', default=ExplorationMode.CAPTAIN,
                                  description='默认是队长模式')
    friend: str = Field(default='', description='friend_name_help')


class DevExploration(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    exploration_config: ExplorationConfig = Field(default_factory=ExplorationConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
