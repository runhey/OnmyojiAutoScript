# This Python file uses the following encoding: utf-8
# @author YLXJ
# github https://github.com/yiliangxiajiao
from pydantic import Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig


class GuibingyanwuConfig(ConfigBase):
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description="limit_time_help")
    # 限制次数
    limit_count: int = Field(default=30, description="limit_count_help")
    # 开启50%经验加成
    exp_50: bool = Field(default=False, description="Buff Exp 50 Click")
    # 开启100%经验加成
    exp_100: bool = Field(default=False, description="Buff Exp 100 Click")


class Guibingyanwu(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    guibingyanwu_config: GuibingyanwuConfig = Field(default_factory=GuibingyanwuConfig)
    general_battle_config: GeneralBattleConfig = Field(
        default_factory=GeneralBattleConfig
    )
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
