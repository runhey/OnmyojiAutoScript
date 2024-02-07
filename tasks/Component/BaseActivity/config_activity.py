# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import time, timedelta
from pydantic import BaseModel, Field, validator
from enum import Enum

from module.logger import logger

from tasks.Component.config_base import ConfigBase, TimeDelta, Time

class ApMode(str, Enum):
    AP_ACTIVITY = 'ap_activity'
    AP_GAME = 'ap_game'


class GeneralClimb(ConfigBase):
    # 限制执行的时间
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    # 限制执行的次数
    limit_count: int = Field(default=50, description='limit_count_help')
    # 每日使用体力挑战的最大次数，默认是300
    ap_game_max: int = Field(default=1800, description='ap_game_max_help')
    # 爬塔活动挂活动的体力还是游戏的体力
    ap_mode: ApMode = Field(default=ApMode.AP_ACTIVITY, description='ap_mode_help')
    # 游戏体力不足是否需要话勾玉购买
    # buy_ap_activity: bool = Field(default=False, description='buy_ap_activity_help')  # 该功能已经废弃
    # 如果挂完的活动的体力，是不是需要挂游戏的体力
    # 在我的设计理念中：活动体力>游戏体力。所以不提供从300挂满然后才到挂活动币
    activity_toggle: bool = Field(default=False, description='activity_toggle_help')

    @validator('limit_time', pre=True, always=True)
    def parse_limit_time(cls, value):
        if isinstance(value, str):
            if value.isdigit():
                try:
                    value = int(value)
                except ValueError:
                    logger.warning('Invalid limit_time value. Expected format: seconds')
                    return time(hour=0, minute=30, second=0)
                delta = timedelta(seconds=value)
                return time(hour=delta.seconds // 3600, minute=delta.seconds // 60 % 60, second=delta.seconds % 60)
            else:
                try:
                    return time.fromisoformat(value)
                except ValueError:
                    logger.warning('Invalid limit_time value. Expected format: HH:MM:SS')
                    return time(hour=0, minute=30, second=0)
        return value

    @validator('ap_game_max', pre=True, always=True)
    def reset_game_max(cls, value):
        def_value = int(300)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                logger.warning('Invalid ap_game_max value. Expected format: int')
                return def_value
        elif isinstance(value, int):
            return def_value
        return def_value


