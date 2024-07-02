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
    Gold = 1     #金币协作
    Jade = 2     #勾玉协作
    Food = 4     #狗/猫粮协作   
    Sushi = 8    #体力协作


class CooperationSelectMask(int, Enum):
    """
        掩码,对协作任务进行筛选
    """
    NoInvite = 0                #不自动邀请
    GoldOnly = 1                #仅 金币 协作进行邀请
    JadeOnly = 2                #仅 勾玉 协作进行邀请
    GoldAndJade = 3
    FoodOnly = 4                #仅 狗/猫粮 协作进行邀请
    GoldAndFood = 5    
    JadeAndFood = 6
    GoldAndJadeAndFood = 7
    SushiOnly = 8               #仅 体力 协作进行邀请
    GoldAndSushi = 9            
    JadeAndSushi = 10
    GoldAndJadeAndSushi = 11
    FoodAndSushi = 12
    GoldAndFoodAndSushi = 13
    JadeAndFoodAndSushi = 14
    Any = 15                    #所有协作任务都邀请


class CooperationSelectMaskDescription(str, Enum):
    # NoInvite = '不邀请'
    # GoldOnly = '仅金币'
    # JadeOnly = '仅勾协'
    # GoldAndJade = '金币和勾协'
    # FoodOnly = '仅食协'
    # GoldAndFood = '金币+食协'
    # JadeAndFood = '勾协+食协'
    # GoldAndJadeAndFood = '金币+勾协+食协'
    # SushiOnly = '仅体协'
    # GoldAndSushi = '金币+体协'
    # JadeAndSushi = '勾协+体协'
    # GoldAndJadeAndSushi = '金币+勾协+体协'
    # FoodAndSushi = '食协+体协'
    # GoldAndFoodAndSushi = '金币+食协+体协'
    # JadeAndFoodAndSushi = '勾协+食协+体协'
    # Any = '全部'
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
    invite_friend_name: str = Field(default=str(""), description="invite_friend_name_help")
    cooperation_type: CooperationSelectMaskDescription = Field(default=CooperationSelectMaskDescription.Any, description="cooperation_type_help")



class WantedQuests(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    wanted_quests_config: WantedQuestsConfig = Field(default_factory=WantedQuestsConfig)
