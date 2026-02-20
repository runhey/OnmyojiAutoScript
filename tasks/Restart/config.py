# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import string

from pydantic import BaseModel, Field

from tasks.Restart.config_scheduler import RestartScheduler
from tasks.Component.config_base import ConfigBase, DateTime, MultiLine


class HarvestConfig(BaseModel):
    # 默认启用
    enable: bool = Field(default=True, description='harvest_enable_help')
    # 永久勾玉卡
    enable_jade: bool = Field(default=True)
    # 签到
    enable_sign: bool = Field(default=True)
    # 999天的签到福袋
    enable_sign_999: bool = Field(default=True)
    # 邮件
    enable_mail: bool = Field(default=True)
    # 御魂加成
    enable_soul: bool = Field(default=True)
    # 体力
    enable_ap: bool = Field(default=True)


class TasksReset(BaseModel):
    reset_task_datetime_enable: bool = Field(default=False, description='reset_task_datetime_enable_help')
    reset_task_datetime: DateTime = Field(default="2023-01-01 00:00:00", description='rest_task_datetime_help')


class LoginCharacterConfig(BaseModel):
    # 同账号同服务器多个角色时,需要登录的角色名/服务器名
    character: str = Field(default="")


class Restart(ConfigBase):
    scheduler: RestartScheduler = Field(default_factory=RestartScheduler)
    tasks_config_reset: TasksReset = Field(default_factory=TasksReset)
    harvest_config: HarvestConfig = Field(default_factory=HarvestConfig)
    login_character_config: LoginCharacterConfig = Field(default_factory=LoginCharacterConfig)
