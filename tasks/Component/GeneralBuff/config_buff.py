# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field


# 这个类是用来 演示的

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


