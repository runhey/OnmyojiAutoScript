# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import time, timedelta
from pydantic import BaseModel, Field
from enum import Enum

from tasks.Component.config_base import ConfigBase, TimeDelta

class ApMode(str, Enum):
    AP_ACTIVITY = 'ap_activity'
    AP_GAME = 'ap_game'


class GeneralClimb(ConfigBase):
    # 限制执行的时间
    limit_time: TimeDelta = Field(default=TimeDelta(hours=1), description='limit_time_help')
    # 限制执行的次数
    limit_count: int = Field(default=50, description='limit_count_help')
    # 每日使用体力挑战的最大次数，默认是300
    ap_game_max: int = Field(default=300, description='ap_game_max_help')
    # 爬塔活动挂活动的体力还是游戏的体力
    ap_mode: ApMode = Field(default=ApMode.AP_ACTIVITY, description='ap_mode_help')
    # 游戏体力不足是否需要话勾玉购买
    # buy_ap_activity: bool = Field(default=False, description='buy_ap_activity_help')  # 该功能已经废弃
    # 如果挂完的活动的体力，是不是需要挂游戏的体力
    # 在我的设计理念中：活动体力>游戏体力。所以不提供从300挂满然后才到挂活动币
    activity_toggle: bool = Field(default=False, description='activity_toggle_help')


