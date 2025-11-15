# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import datetime, time

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, DateTime, TimeDelta, Time
from tasks.BondlingFairyland.config_battle import BattleConfig
from tasks.Component.GeneralInvite.config_invite import InviteConfig


class BondlingMode(str, Enum):
    MODE1 = '只刷探查(仅限单刷)'
    MODE2 = '只刷契灵(低级式盘)'
    MODE3 = '只刷契灵(中级式盘)'
    MODE4 = '只刷契灵(高级式盘)'


class BondlingClass(str, Enum):
    TOMB_GUARD = '镇墓兽'
    AZURE_BASAN = '火灵'
    SNOWBALL = '茨球'
    LITTLE_KURO = '小黑'

    BONDLING_2_1 = '针女'
    BONDLING_2_2 = '薙魂'
    BONDLING_2_3 = '月魔兔'
    BONDLING_2_4 = '狐火'

    @staticmethod
    def get_index(value) -> int:
        """根据枚举值或枚举返回对应顺序（从1开始）"""
        if isinstance(value, BondlingClass):
            member = value
        else:
            try:
                member = BondlingClass(value)
            except ValueError:
                return None
        return list(BondlingClass).index(member) + 1


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
    bondling_mode: BondlingMode = Field(default=BondlingMode.MODE1,
                                        description='只刷探查:自动切换契灵对应地域\n低级式盘:自动切换非连续,非羁绊\n中级式盘:自动切换连续,羁绊')
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    limit_count: int = Field(default=30, description='limit_count_help')
    bondling_stone_class: BondlingClass = Field(default=BondlingClass.TOMB_GUARD, description='设置需要刷的契灵')
    bondling_stone_enable: bool = Field(default=False, description='没有契灵了是否使用鸣契石购买契灵')
    bondling_search_enable: bool = Field(default=False, description='没有契灵了是否自动探查(要求身份必须是alone,否则此项无效)\n'
                                                                    '若启用了购买契灵则优先购买契灵,购买失败则进行探查\n'
                                                                    '若启用了切换御魂则切换契灵御魂的同时也会切换探查御魂\n'
                                                                    '注:探查耗费的时间与次数也计入总时间和次数中')
    check_enable: bool = Field(default=True, description='是否检查契忆数量')
    limit_num: int = Field(default=2000, description='契忆数量限制,到达此限制将自动结束任务(仅在任务开始时判断)')

    @field_validator("bondling_mode", mode="before")
    def convert_old_value(cls, v):
        old_new_map = {
            "mode_1": "只刷探查(仅限单刷)",
            'mode_2': '只刷契灵(低级式盘)',
            'mode_3': '只刷契灵(中级式盘)'
        }
        return old_new_map.get(v, v)


class BondlingSwitchSoul(ConfigBase):
    enable: bool = Field(default=False,
                         description='若是数字,则以编号方式切换御魂(组号,队伍号),组号1-7,队伍号1-4\n若非数字,则自动以ocr方式切换御魂(组名,队伍名)')
    search_switch: str = Field(default='', description='设置探查御魂装配分组')
    tomb_guard_switch: str = Field(default='', description='tomb_guard_switch_help')
    snowball_switch: str = Field(default='', description='snowball_switch_help')
    little_kuro_switch: str = Field(default='', description='little_kuro_switch_help')
    azure_basan_switch: str = Field(default='', description='azure_basan_switch_help')
    bondling_2_1_switch: str = Field(default='', description='设置针女御魂装配分组')
    bondling_2_2_switch: str = Field(default='', description='设置薙魂御魂装配分组')
    bondling_2_3_switch: str = Field(default='', description='设置月魔兔御魂装配分组')
    bondling_2_4_switch: str = Field(default='', description='设置狐火御魂装配分组')

    def get_switch_by_enum(self, bondling_enum: BondlingClass) -> tuple[str, tuple[str | int, str | int]]:
        """根据枚举获取对应的 切换类型, (group,team)"""
        return self.get_switch_by_name(f"{bondling_enum.name.lower()}_switch")

    def get_switch_by_name(self, switch_name: str) -> tuple[str, tuple[str | int, str | int]]:
        """根据名称获取对应的御魂预设"""
        group_team = getattr(self, switch_name, None)
        if group_team is None or group_team.strip() == '' or ',' not in group_team or len(group_team.split(',')) != 2:
            return None, (None, None)
        group, team = group_team.split(',')
        if group.isdigit() and team.isdigit():
            return 'int', (int(group), int(team))
        return 'str', (group, team)


class BondlingFairyland(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    bondling_config: BondlingConfig = Field(default_factory=BondlingConfig)
    invite_config: InviteConfig = Field(default_factory=InviteConfig)
    bondling_switch_soul: BondlingSwitchSoul = Field(default_factory=BondlingSwitchSoul)
    battle_config: BattleConfig = Field(default_factory=BattleConfig)
