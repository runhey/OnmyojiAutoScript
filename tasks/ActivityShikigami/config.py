# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import time, timedelta
from pydantic import BaseModel, Field

from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, TimeDelta
from tasks.Component.BaseActivity.config_activity import GeneralClimb


class ShikigamiType(str, Enum):
    FOOD_TYPE_1 = 'shikigami_type_1'
    FOOD_TYPE_2 = 'shikigami_type_2'
    FOOD_TYPE_3 = 'shikigami_type_3'
    FOOD_TYPE_4 = 'shikigami_type_4'


class SwitchSoulConfig(BaseModel):
    # 切换门票爬塔御魂
    enable_switch_pass: bool = Field(default=False, description='是否切换门票爬塔御魂')
    pass_group_team: str = Field(default='-1,-1', description='组1-7,队伍1-4 中间用英文,分隔。战斗内切换队伍预设使用该值')
    enable_switch_pass_by_name: bool = Field(default=False, description='是否通过ocr切换御魂')
    pass_group_team_name: str = Field(default='', description='组名,队伍名 中间用英文,分隔')
    # 切换体力爬塔御魂
    enable_switch_ap: bool = Field(default=False, description='是否切换体力爬塔御魂')
    ap_group_team: str = Field(default='-1,-1', description='组1-7,队伍1-4 中间用英文,分隔。战斗内切换队伍预设使用该值')
    enable_switch_ap_by_name: bool = Field(default=False, description='是否通过ocr切换御魂')
    ap_group_team_name: str = Field(default='', description='组名,队伍名 中间用英文,分隔')
    # 切换boss爬塔御魂
    enable_switch_boss: bool = Field(default=False, description='是否切换boss爬塔御魂')
    boss_group_team: str = Field(default='-1,-1', description='组1-7,队伍1-4 中间用英文,分隔。战斗内切换队伍预设使用该值')
    enable_switch_boss_by_name: bool = Field(default=False, description='是否通过ocr切换御魂')
    boss_group_team_name: str = Field(default='', description='组名,队伍名 中间用英文,分隔')


class GeneralBattleConfig(BaseModel):
    # 是否切换门票爬塔预设
    enable_pass_preset: bool = Field(default=False, description='是否切换门票爬塔预设')
    # 是否开启门票爬塔绿标
    enable_pass_green: bool = Field(default=False, description='是否开启门票爬塔绿标')
    # 门票爬塔绿标位置
    pass_green_mark: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='门票爬塔绿标位置')
    # 门票爬塔战斗过程是否随机点击或滑动
    enable_pass_anti_detect: bool = Field(default=False, description='门票爬塔战斗过程是否随机点击或滑动')

    # 是否切换体力爬塔预设
    enable_ap_preset: bool = Field(default=False, description='是否切换体力爬塔预设')
    # 是否开启体力爬塔绿标
    enable_ap_green: bool = Field(default=False, description='是否开启体力爬塔绿标')
    # 体力爬塔绿标位置
    ap_green_mark: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='体力爬塔绿标位置')
    # 体力爬塔战斗过程是否随机点击或滑动
    enable_ap_anti_detect: bool = Field(default=False, description='体力爬塔战斗过程是否随机点击或滑动')

    # 是否切换boss爬塔预设
    enable_boss_preset: bool = Field(default=False, description='是否切换boss爬塔预设')
    # 是否开启boss爬塔绿标
    enable_boss_green: bool = Field(default=False, description='是否开启boss爬塔绿标')
    # boss爬塔绿标位置
    boss_green_mark: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='boss爬塔绿标位置')
    # boss爬塔战斗过程是否随机点击或滑动
    enable_boss_anti_detect: bool = Field(default=False, description='boss爬塔战斗过程是否随机点击或滑动')


class ActivityShikigami(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    general_climb: GeneralClimb = Field(default_factory=GeneralClimb)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    general_battle: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
