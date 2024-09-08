# This Python file uses the following encoding: utf-8
# @author YLXJ
# github https://github.com/yiliangxiajiao
from pydantic import Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig


class BingcangmijingConfig(ConfigBase):
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description="limit_time_help")
    # 限制次数
    limit_count: int = Field(default=30, description="limit_count_help")
    # buff选择优先级
    custom_buff_priority: str = Field(default="")


class Bingcangmijing(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    bingcangmijing_config: BingcangmijingConfig = Field(
        default_factory=BingcangmijingConfig
    )
    general_battle_config: GeneralBattleConfig = Field(
        default_factory=GeneralBattleConfig
    )
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
