# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import time, timedelta
from pydantic import BaseModel, Field, validator, field_validator
from enum import Enum

from module.logger import logger

from tasks.Component.config_base import ConfigBase, TimeDelta, Time


class ApMode(str, Enum):
    AP_ACTIVITY = 'ap_activity'
    AP_GAME = 'ap_game'


class GeneralClimb(ConfigBase):
    # 限制执行的时间
    limit_time: Time = Field(default=Time(minute=30), description='限制爬塔运行时间')
    # 限制门票爬塔的次数
    pass_limit: int = Field(default=50, description='门票爬塔的最大次数')
    # 限制体力爬塔的次数
    ap_limit: int = Field(default=300, description='体力爬塔的最大次数')
    # 限制boss战爬塔的次数
    boss_limit: int = Field(default=20, description='boss战爬塔的最大次数')
    # 启用门票爬塔
    enable_pass: bool = Field(default=True, description='是否启用门票爬塔')
    # 启用体力爬塔
    enable_ap: bool = Field(default=True, description='是否启用体力爬塔')
    # 启用boss战爬塔
    enable_boss: bool = Field(default=True, description='是否启用boss战爬塔')
    # 爬塔运行顺序
    run_sequence: str = Field(default='pass,boss,ap',
                              description='爬塔运行顺序,英文逗号分隔,从左到右运行,若没启用自动跳过对应类型(pass:门票,boss:boss战,ap:体力)')
    # 门票爬塔buff
    pass_buff: str = Field(default='buff_4,buff_5', description='门票爬塔加成,buff1-5,加成页从左往右顺序')
    # 体力爬塔buff
    ap_buff: str = Field(default='buff_4,buff_5', description='体力爬塔加成,buff1-5,加成页从左往右顺序')
    # boss爬塔buff
    boss_buff: str = Field(default='buff_1,buff_3', description='boss战爬塔加成,buff1-5,加成页从左往右顺序')
    # 结束后激活 御魂清理
    active_souls_clean: bool = Field(default=False, description='是否运行结束后清理御魂')
    # 点击战斗随机休息
    random_sleep: bool = Field(default=False, description='是否启用在点击战斗前随机休息')

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
