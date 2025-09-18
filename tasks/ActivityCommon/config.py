# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.config_scheduler import Scheduler


class ActivityCommonConfig(BaseModel):
    enable: bool = Field(default=False, description='auto_enable_help')
    # 限制次数
    limit_count: int = Field(default=200, description='limit_count_help')
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    # 结束后激活 御魂清理
    active_souls_clean: bool = Field(default=False, description='active_souls_clean_help')


class ActivityCommon(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    activity_common_config: ActivityCommonConfig = Field(default_factory=ActivityCommonConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)




