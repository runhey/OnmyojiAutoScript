# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field


# 这个类是用来 演示的
class BuffClass(Enum):
    AWAKE = 10  # 觉醒
    SOUL = 20  # 御魂
    GOLD_50 = 30  # 金币50
    GOLD_100 = 40  # 金币100
    EXP_50 = 50  # 经验50
    EXP_100 = 60  # 经验100
    AWAKE_CLOSE = 70  # 觉醒
    SOUL_CLOSE = 80  # 御魂
    GOLD_50_CLOSE = 90  # 金币50
    GOLD_100_CLOSE = 100  # 金币100
    EXP_50_CLOSE = 110  # 经验50
    EXP_100_CLOSE = 120  # 经验100


class BuffConfig(BaseModel):
    # 是否启动buff
    buff_enable: bool = Field(default=False, description='buff_enable_help')
    # 是否点击觉醒Buff
    buff_awake_click: bool = Field(default=False, description='')
    # 是否点击御魂buff
    buff_soul_click: bool = Field(default=False, description='')
    # 是否点击金币50buff
    buff_gold_50_click: bool = Field(default=False, description='')
    # 是否点击金币100buff
    buff_gold_100_click: bool = Field(default=False, description='')
    # 是否点击经验50buff
    buff_exp_50_click: bool = Field(default=False, description='')
    # 是否点击经验100buff
    buff_exp_100_click: bool = Field(default=False, description='')


