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
    # MEMBER = 'member'
    # ALONE = 'alone'
    # WILD = 'wild'

class Layer(str, Enum):
    ONE = '壹层'
    TWO = '贰层'
    THREE = '叁层'
    FOUR = '肆层'
    FIVE = '伍层'
    SIX = '陆层'
    SEVEN = '柒层'
    EIGHT = '捌层'
    NINE = '玖层'
    TEN = '拾层'
    ELEVEN = '悲鸣'
    TWELVE = '神罚'

class OrochiMoansConfig(ConfigBase):
    # 身份
    user_status: UserStatus = Field(default=UserStatus.LEADER, description='user_status_help')
    # 层数
    layer: Layer = Field(default=Layer.ELEVEN, description='layer_help')
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    # 限制次数
    limit_count: int = Field(default=30, description='limit_count_help')
    # 是否开启御魂加成
    soul_buff_enable: bool = Field(default=False, description='soul_buff_enable_help')
    # # 是否检测突破券数量（不支持五倍活动）
    # limit_by_toppa_scrolls_enable: bool = Field(default=False, description='limit_count_by_toppa_scrolls_enable_help')
    # # 突破券数量上限（不支持五倍活动）
    # limit_by_toppa_scrolls_count: int = Field(default=30, description='limit_count_by_toppa_scrolls_count_help')

class OrochiMoans(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    orochi_moans_config: OrochiMoansConfig = Field(default_factory=OrochiMoansConfig)
    invite_config: InviteConfig = Field(default_factory=InviteConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
