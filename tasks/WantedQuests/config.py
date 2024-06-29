# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta, time
from enum import Enum
from pydantic import BaseModel, Field, validator

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig


class CooperationType(int, Enum):
    """
        用于区分悬赏封印协作类型
    """
    Gold = 1
    Jade = 2
    Food = 4
    Sushi = 8


class CooperationSelectMask(int, Enum):
    NoInvite = 0
    GoldOnly = 1
    JadeOnly = 2
    GoldAndJade = 3
    FoodOnly = 4
    GoldAndFood = 5
    JadeAndFood = 6
    GoldAndJadeAndFood = 7
    SushiOnly = 8
    GoldAndSushi = 9
    JadeAndSushi = 10
    GoldAndJadeAndSushi = 11
    FoodAndSushi = 12
    GoldAndFoodAndSushi = 13
    JadeAndFoodAndSushi = 14
    Any = 15


class CooperationSelectMaskDescription(str, Enum):
    NoInvite = 'NoInvite'
    GoldOnly = 'GoldOnly'
    JadeOnly = 'JadeOnly'
    GoldAndJade = 'GoldAndJade'
    FoodOnly = 'FoodOnly'
    GoldAndFood = 'GoldAndFood'
    JadeAndFood = 'JadeAndFood'
    GoldAndJadeAndFood = 'GoldAndJadeAndFood'
    SushiOnly = 'SushiOnly'
    GoldAndSushi = 'GoldAndSushi'
    JadeAndSushi = 'JadeAndSushi'
    GoldAndJadeAndSushi = 'GoldAndJadeAndSushi'
    FoodAndSushi = 'FoodAndSushi'
    GoldAndFoodAndSushi = 'GoldAndFoodAndSushi'
    JadeAndFoodAndSushi = 'JadeAndFoodAndSushi'
    Any = 'Any'


class WantedQuestsConfig(BaseModel):
    before_end: Time = Field(default=Time(0, 0, 0), description='before_end_help')
    invite_friend_name: str = Field(default=str(""), description="协作任务邀请特定人员")
    cooperation_type: CooperationSelectMaskDescription = Field(default=CooperationSelectMaskDescription.Any, description="协作悬赏类型,其余协作任务不会邀请特定人员.仅当邀请特定人员时生效")



class WantedQuests(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    wanted_quests_config: WantedQuestsConfig = Field(default_factory=WantedQuestsConfig)
