# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time

from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, DateTime, TimeDelta, Time
from tasks.BondlingFairyland.config_battle import BattleConfig
from tasks.Component.GeneralInvite.config_invite import InviteConfig
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig

class BondlingMode(str, Enum):
    MODE1 = 'mode_1'
    MODE2 = 'mode_2'
    MODE3 = 'mode_3'
# 镇墓兽 Tomb Guard  tomb_guard
# 茨球 Snowball       snowball
# 小黑 Little Kuro  little_kuro
# 火灵 Azure Basan azure_basan
class BondlingClass(str, Enum):
    TOMB_GUARD = '镇墓兽'
    SNOWBALL = '茨球'
    LITTLE_KURO = '小黑'
    AZURE_BASAN = '火灵'

# 契石 Bondling Stone
# 低级契灵盘 Low Bondling Discs
# 中级契灵盘 Medium Bondling Discs
# 高级契灵盘 High Bondling Discs
class UserStatus(str, Enum):
    LEADER = 'leader'
    MEMBER = 'member'
    ALONE = 'alone'
    handoff1 = 'handoff1'
    handoff2 = 'handoff2'
    # WILD = 'wild'  # 还不打算实现
class BondlingConfig(ConfigBase):
    # 身份
    user_status: UserStatus = Field(default=UserStatus.ALONE, description='user_status_help')
    bondling_mode: BondlingMode = Field(default=BondlingMode.MODE1, description='bondling_mode_help')
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    limit_count: int = Field(default=30, description='limit_count_help')
    bondling_stone_enable: bool = Field(default=False, description='bondling_stone_enable_help')
    bondling_stone_class: BondlingClass = Field(default=BondlingClass.TOMB_GUARD, description='bondling_stone_class_help')

class BondlingSwitchSoul(ConfigBase):
    auto_switch_soul: bool = Field(default=False, description='auto_switch_soul_help')
    # 镇墓兽 config
    tomb_guard_switch: str = Field(default='-1,-1', description='tomb_guard_switch_help')
    # 茨球 config
    snowball_switch: str = Field(default='-1,-1', description='snowball_switch_help')
    # 小黑 config
    little_kuro_switch: str = Field(default='-1,-1', description='little_kuro_switch_help')
    # 火灵 config
    azure_basan_switch: str = Field(default='-1,-1', description='azure_basan_switch_help')

class BondlingFairyland(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    bondling_config: BondlingConfig = Field(default_factory=BondlingConfig)
    bondling_switch_soul: BondlingSwitchSoul = Field(default_factory=BondlingSwitchSoul)
    invite_config: InviteConfig = Field(default_factory=InviteConfig)
    battle_config: BattleConfig = Field(default_factory=BattleConfig)
    # battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)

    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)





