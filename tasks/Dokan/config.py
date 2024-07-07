# This Python file uses the following encoding: utf-8
# @brief    Configurations for Ryou Dokan Toppa (阴阳竂道馆突破配置)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas

from pydantic import BaseModel, Field
from enum import Enum
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.config_scheduler import Scheduler



class DokanConfig(BaseModel):
    # # 寮管理开启道馆
    # dokan_declare_war: bool = Field(default=False, description='dokan_declare_war_help')
    # # 选择哪一个竂
    # dokan_declear_war_priority: int = Field(default=0, description='dokan_declear_war_priority_help')

    # 攻击优先顺序: 见习=0,初级=1...
    dokan_attack_priority: int = Field(default=0, description='dokan_attack_priority_help')

    # 失败CD后自动加油
    dokan_auto_cheering_while_cd: bool = Field(default=False, description='dokan_auto_cheering_while_cd_help')

    # 正式进攻会设定 2s - 10s 的随机延迟，避免攻击间隔及其相近被检测为脚本。
    random_delay: bool = Field(default=False, description='random_delay_help')

    # 防封：使用固定的随机区域进行随机点击，若为False将自动识别当前画面中的最大纯色区域作为随机点击区域
    anti_detect_click_fixed_random_area: bool = Field(default=False, description='anti_detect_click_fixed_random_area_help')

class Dokan(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    dokan_config: DokanConfig = Field(default_factory=DokanConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)