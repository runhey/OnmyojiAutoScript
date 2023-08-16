# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase
from tasks.Orochi.config import UserStatus


class Layer(str, Enum):
    ONE = '壹层'
    TWO = '贰层'
    THREE = '叁层'
    FOUR = '肆层'

class EternitySeaConfig(ConfigBase):
    # 身份
    user_status: UserStatus = Field(default=UserStatus.LEADER, description='user_status_help')
    # 层数
    layer: Layer = Field(default=Layer.FOUR, description='layer_help')
    # 限制时间
    limit_time: time = Field(default=time(minute=30), description='limit_time_help')
    # 限制次数
    limit_count: int = Field(default=50, description='limit_count_help')

class EternitySea(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    eternity_sea_config: EternitySeaConfig = Field(default_factory=EternitySeaConfig)

