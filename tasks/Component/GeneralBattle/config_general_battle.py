# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field

class GreenMarkType(str, Enum):
    GREEN_LEFT1 = 'green_left1'
    GREEN_LEFT2 = 'green_left2'
    GREEN_LEFT3 = 'green_left3'
    GREEN_LEFT4 = 'green_left4'
    GREEN_LEFT5 = 'green_left5'
    GREEN_MAIN = 'green_main'

class GeneralBattleConfig(BaseModel):

    # 是否锁定阵容, 有些的战斗是外边的锁定阵容甚至有些的战斗没有锁定阵容的
    lock_team_enable: bool = Field(default=False, description='[锁定阵容]:默认为False \n如果锁定阵容将无法启用预设队伍、加成功能')

    # 是否启动 预设队伍
    preset_enable: bool = Field(default=False, description='[启用预设]:默认为False')
    # 选哪一个预设组
    preset_group: int = Field(default=1, description='[设置预设组]:默认为1, 可选[1-7]', ge=1, le=7)
    # 选哪一个队伍
    preset_team: int = Field(default=1, description='[设置预设队伍]:默认为1, 可选[1-5]', ge=1, le=5)
    # 是否启动开启buff
    buff_enable: bool = Field(default=False, description='[启用加成]:默认为False')
    # 是否点击觉醒Buff
    buff_awake_click: bool = Field(default=False, description='[觉醒加成]:默认为False')
    # 是否点击御魂buff
    buff_soul_click: bool = Field(default=False, description='[御魂加成]:默认为False')
    # 是否点击金币50buff
    buff_gold_50_click: bool = Field(default=False, description='[金币50加成]:默认为False')
    # 是否点击金币100buff
    buff_gold_100_click: bool = Field(default=False, description='[金币100加成]:默认为False')
    # 是否点击经验50buff
    buff_exp_50_click: bool = Field(default=False, description='[经验50加成]:默认为False')
    # 是否点击经验100buff
    buff_exp_100_click: bool = Field(default=False, description='[经验100加成]:默认为False')

    # 是否开启绿标
    green_enable: bool = Field(default=False, description='[启用绿标]:默认为False')
    # 选哪一个绿标
    green_mark: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='[设置绿标]:默认为左一 \n可选[左一, 左二, 左三, 左四, 左五, 主阴阳师]')

    # 是否启动战斗时随机点击或者随机滑动
    random_click_swipt_enable: bool = Field(default=False, description='[战斗时随机点击或滑动]:默认为False \n防封优化，请注意这个与绿标功能冲突，可能会乱点绿标')


