# This Python file uses the following encoding: utf-8
# @author TripleEarth
# github https://github.com/TripleEarth
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time

from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.GeneralInvite.config_invite import InviteConfig
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig


class UserStatus(str, Enum):
    LEADER = 'leader'
    MEMBER = 'member'
    ALONE = 'alone'
    WILD = 'wild'  # 还不打算实现


class Layer(str, Enum):
    ONE = '壹层'
    TWO = '贰层'
    THREE = '叁层'
    FOUR = '日蚀'


class FallenSunConfig(ConfigBase):
    # 身份
    user_status: UserStatus = Field(default=UserStatus.LEADER, description='user_status_help')
    # 层数
    layer: Layer = Field(default=Layer.THREE, description='layer_help')
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    # 限制次数
    limit_count: int = Field(default=50, description='limit_count_help')


class FallenSun(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    fallen_sun_config: FallenSunConfig = Field(default_factory=FallenSunConfig)
    invite_config: InviteConfig = Field(default_factory=InviteConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
