# This Python file uses the following encoding: utf-8
# @brief    Configurations for Ryou Dokan Toppa (阴阳竂道馆突破配置)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas

from pydantic import BaseModel, Field
from pygments.lexer import default
from scripts.regsetup import description
from sympy.testing.pytest import Failed

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.config_scheduler import Scheduler

class AbyssShadowsTime(ConfigBase):
    # 自定义运行时间
    custom_run_time_friday: Time = Field(default=Time(hour=19, minute=0, second=0))
    custom_run_time_saturday: Time = Field(default=Time(hour=19, minute=0, second=0))
    custom_run_time_sunday: Time = Field(default=Time(hour=19, minute=0, second=0))

class AbyssShadowsCombatTime(BaseModel):
    # 设置战斗时间
    CombatTime_enable: bool = Field(default=False, description="开启智能伤害")
    boss_combat_time: int = Field(default=60, description="以秒为单位设置首领战斗时间，请合理设置")
    general_combat_time: int = Field(default=60, description="以秒为单位设置副将战斗时间，请合理设置")
    elite_combat_time: int = Field(default=60, description="以秒为单位设置精英战斗时间，请合理设置")

class AbyssShadows(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    abyss_shadows_time: AbyssShadowsTime = Field(default_factory=AbyssShadowsTime)
    abyss_shadows_combat_time: AbyssShadowsCombatTime = Field(default_factory=AbyssShadowsCombatTime)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
