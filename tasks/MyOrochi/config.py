from pydantic import BaseModel, Field
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler
from enum import Enum


class RoleMode(str, Enum):
    CAPTAIN = '队长'
    MEMBER = '队员'


class MyOrochiConfig(BaseModel):
    mode: RoleMode = Field(title='角色模式', default=RoleMode.CAPTAIN, description='默认是队长模式')


class MyOrochi(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    orochi_config: MyOrochiConfig = Field(default_factory=MyOrochiConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
