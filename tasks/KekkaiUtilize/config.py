# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, TimeDelta
from tasks.Utils.config_enum import ShikigamiClass

class SelectFriendList(str, Enum):
    SAME_SERVER = 'same_server'
    DIFFERENT_SERVER = 'different_server'

class UtilizeRule(str, Enum):
    DEFAULT = 'default'  # 默认就好
    TAIKO = 'kaiko'  # 太鼓优先
    FISH = 'fish'  # 斗鱼优先
    # AUTO = 'auto'  # 自动 兼容代码罢了



class UtilizeScheduler(Scheduler):
    priority: int = Field(default=2, description='priority_help')
    success_interval: TimeDelta = Field(default=TimeDelta(hours=6), description='success_interval_help')
    failure_interval: TimeDelta = Field(default=TimeDelta(hours=6), description='failure_interval_help')

class UtilizeConfig(BaseModel):
    utilize_rule: UtilizeRule = Field(default=UtilizeRule.DEFAULT, description='utilize_rule_help')
    select_friend_list: SelectFriendList = Field(default=SelectFriendList.SAME_SERVER, description='select_friend_list_help')
    shikigami_class: ShikigamiClass = Field(default=ShikigamiClass.N, description='shikigami_class_help')
    shikigami_order: int = Field(default=4, description='shikigami_order_help')
    harvest_guild_max_times: int = Field(default=3, description='收取寮资金或体力失败的最大尝试次数')
    utilize_enable: bool = Field(default=True, description='是否蹭卡，小号可以选择不蹭卡')
    guild_ap_enable: bool = Field(default=True, description='guild_ap_enable_help')
    guild_assets_enable: bool = Field(default=True, description='guild_assets_enable_help')
    box_ap_enable: bool = Field(default=True, description='box_ap_enable_help')
    box_exp_enable: bool = Field(default=True, description='box_exp_enable_help')
    box_exp_waste: bool = Field(default=True, description='box_exp_waste_help')


class KekkaiUtilize(ConfigBase):
    scheduler: UtilizeScheduler = Field(default_factory=UtilizeScheduler)
    utilize_config: UtilizeConfig = Field(default_factory=UtilizeConfig)



