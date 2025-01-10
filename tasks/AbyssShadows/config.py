# This Python file uses the following encoding: utf-8
# @brief    Configurations for Ryou Dokan Toppa (阴阳竂道馆突破配置)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from tasks.AbyssShadows.assets import AbyssShadowsAssets
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase, Time, DateTime
from tasks.Component.config_scheduler import Scheduler
from cached_property import cached_property


class AreaType:
    """ 暗域类型 """
    DRAGON = AbyssShadowsAssets.I_ABYSS_DRAGON  # 神龙暗域
    PEACOCK = AbyssShadowsAssets.I_ABYSS_PEACOCK  # 孔雀暗域
    FOX = AbyssShadowsAssets.I_ABYSS_FOX  # 白藏主暗域
    LEOPARD = AbyssShadowsAssets.I_ABYSS_LEOPARD  # 黑豹暗域

    @cached_property
    def name(self) -> str:
        """

        :return:
        """
        return Path(self.file).stem.upper()

    def __str__(self):
        return self.name

    __repr__ = __str__


class CilckArea:
    """ 点击区域 """
    GENERAL_1 = AbyssShadowsAssets.C_GENERAL_1_CLICK_AREA
    GENERAL_2 = AbyssShadowsAssets.C_GENERAL_2_CLICK_AREA
    ELITE_1 = AbyssShadowsAssets.C_ELITE_1_CLICK_AREA
    ELITE_2 = AbyssShadowsAssets.C_ELITE_2_CLICK_AREA
    ELITE_3 = AbyssShadowsAssets.C_ELITE_3_CLICK_AREA
    BOSS = AbyssShadowsAssets.C_BOSS_CLICK_AREA

    @cached_property
    def name(self) -> str:
        """

        :return:
        """
        return Path(self.file).stem.upper()

    def __str__(self):
        return self.name

    __repr__ = __str__


class EnemyType(Enum):
    """ 敌人类型 """
    BOSS = 1  # 首领
    GENERAL = 2  # 副将
    ELITE = 3  # 精英


class AbyssShadowsTime(ConfigBase):
    # 自定义运行时间
    custom_run_time_friday: Time = Field(default=Time(hour=19, minute=0, second=0))
    custom_run_time_saturday: Time = Field(default=Time(hour=19, minute=0, second=0))
    custom_run_time_sunday: Time = Field(default=Time(hour=19, minute=0, second=0))
    # 尝试主动开启狭间-区别于游戏中的自动开启狭间功能
    try_start_abyss_shadows: bool = Field(default=False, description='try_start_abyss_shadows_help')


class ProcessManage(ConfigBase):
    # 攻击顺序 A,B,C,D 分别表示四个区域，123456表示区域内6个怪物，从上到下，从左到右的顺序
    #           1
    #       2       3
    #   4       5       6
    # 之间用-分隔，不同怪物用;分隔
    # 小蛇使用E,-后面表示打几只,例如E-2表示打两只小蛇
    # 例如 A-1;B-2;C-3...
    attack_order: str = Field(default='', description='attack_order_help')
    # 标记主怪,与攻击顺序类似,可以根据类单独设置
    # 例如 A;2;3;C-4;D-6
    mark_main: str = Field(default='', description='mark_boss_help')
    # 首领预设
    preset_boss: str = Field(default='', description='preset_boss_help')
    # 副将预设
    preset_general: str = Field(default='', description='preset_general_help')
    # 精英预设
    preset_elite: str = Field(default='', description='preset_elite_help')
    # 小蛇预设
    preset_snake: str = Field(default='', description='preset_snake_help')
    # 首领策略 等待打完/时间到了退出/伤害足够退出/秒退
    strategy_boss: str = Field(default='', description='strategy_boss_help')
    # 副将策略
    strategy_general: str = Field(default='', description='strategy_general_help')
    # 精英策略
    strategy_elite: str = Field(default='', description='strategy_elite_help')

    def parse_order_item(self, str):
        area, num = str.split('-')
        result = [str]
        match area:
            case 'A':
                result.append(AbyssShadowsAssets.C_ABYSS_DRAGON)
            case 'B':
                result.append(AbyssShadowsAssets.C_ABYSS_PEACOCK)
            case 'C':
                result.append(AbyssShadowsAssets.C_ABYSS_FOX)
            case 'D':
                result.append(AbyssShadowsAssets.C_ABYSS_LEOPARD)
            case _:
                result.append(AbyssShadowsAssets.C_ABYSS_DRAGON)
        match num:
            case '1':
                result.append(AbyssShadowsAssets.C_BOSS_CLICK_AREA)
            case '2':
                result.append(AbyssShadowsAssets.C_GENERAL_1_CLICK_AREA)
            case '3':
                result.append(AbyssShadowsAssets.C_GENERAL_2_CLICK_AREA)
            case '4':
                result.append(AbyssShadowsAssets.C_ELITE_1_CLICK_AREA)
            case '5':
                result.append(AbyssShadowsAssets.C_ELITE_2_CLICK_AREA)
            case '6':
                result.append(AbyssShadowsAssets.C_ELITE_3_CLICK_AREA)
            case _:
                result.append(AbyssShadowsAssets.C_ELITE_1_CLICK_AREA)
        return tuple(result)

    def parse_order(self, value: str) -> list:
        if value == '':
            return []
        tmp = value.split(';')
        for item in tmp:
            result = self.parse_order_item(item)
            yield result

    def is_need_mark_main(self, code):
        def expand_mark_main(mark_main_str: str):
            items = mark_main_str.split(';')
            expanded = []
            for item in items:
                if item == 'A' or item == 'B' or item == 'C' or item == 'D':
                    expanded.append(item + "-1")
                    expanded.append(item + "-2")
                    expanded.append(item + "-3")
                    expanded.append(item + "-4")
                    expanded.append(item + "-5")
                    expanded.append(item + "-6")
                    continue
                if item == '1' or item == '2' or item == '3' or item == '4' or item == '5' or item == '6':
                    expanded.append('A-' + item)
                    expanded.append('B-' + item)
                    expanded.append('C-' + item)
                    expanded.append('D-' + item)
                    continue
                expanded.append(item)
            return expanded

        return code in expand_mark_main(self.mark_main)


class SavedParams(ConfigBase):
    # 已完成
    done: str = Field(default='', description='done_help')
    # 失败
    fail: str = Field(default='', description='fail_help')
    # 已知的已经打完的
    unavailable: str = Field(default='', description='unavailable_help')
    # 当前时间，用于判断存储参数有效性
    today: str = Field(default='2023-01-01', description='today_help')

    # def save(self):
    #     self.today = datetime.today().strftime('yyyy-mm-dd')
    #     self.config.save()


class AbyssShadows(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    abyss_shadows_time: AbyssShadowsTime = Field(default_factory=AbyssShadowsTime)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
