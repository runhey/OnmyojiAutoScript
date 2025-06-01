# This Python file uses the following encoding: utf-8
# @brief    Configurations for Ryou Dokan Toppa (阴阳竂道馆突破配置)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas
from enum import Enum
from module.atom.click import RuleClick
from module.atom.image import RuleImage

from pydantic import BaseModel, Field

from module.base.timer import Timer
from tasks.AbyssShadows.assets import AbyssShadowsAssets
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase, Time, DateTime
from tasks.Component.config_scheduler import Scheduler


class AreaType(Enum):
    """ 暗域类型 """
    DRAGON = AbyssShadowsAssets.I_ABYSS_DRAGON  # 神龙暗域
    PEACOCK = AbyssShadowsAssets.I_ABYSS_PEACOCK  # 孔雀暗域
    FOX = AbyssShadowsAssets.I_ABYSS_FOX  # 白藏主暗域
    LEOPARD = AbyssShadowsAssets.I_ABYSS_LEOPARD  # 黑豹暗域

    # @classmethod
    # def __str__(cls, value):
    #     # 遍历类属性，找到匹配值对应的属性名
    #     for name, attr_value in vars(cls).items():
    #         if attr_value == value and not name.startswith('__'):
    #             return name
    #     return str(value)  # 默认行为


class ClickArea(Enum):
    """ 点击区域 """
    GENERAL_1 = AbyssShadowsAssets.C_GENERAL_1_CLICK_AREA
    GENERAL_2 = AbyssShadowsAssets.C_GENERAL_2_CLICK_AREA
    ELITE_1 = AbyssShadowsAssets.C_ELITE_1_CLICK_AREA
    ELITE_2 = AbyssShadowsAssets.C_ELITE_2_CLICK_AREA
    ELITE_3 = AbyssShadowsAssets.C_ELITE_3_CLICK_AREA
    BOSS = AbyssShadowsAssets.C_BOSS_CLICK_AREA

    # @cached_property
    # def name(self) -> str:
    #     """
    #
    #     :return:
    #     """
    #     return Path(self.file).stem.upper()
    #
    # def __str__(self):
    #     return self.name
    #
    # __repr__ = __str__


class EnemyType(str, Enum):
    """ 敌人类型 """
    BOSS = "BOSS"  # 首领
    GENERAL = "GENERAL"  # 副将
    ELITE = "ELITE"  # 精英


class AbyssShadowsDifficulty(str, Enum):
    EASY = "EASY"
    NORMAL = "NORMAL"
    HARD = "HARD"


class Code(str):
    def __init__(self, value: str):
        self.value = value

    def get_areatype(self):
        area, num = self.value.split('-')
        match area:
            case 'A':
                return AreaType.DRAGON
            case 'B':
                return AreaType.PEACOCK
            case 'C':
                return AreaType.FOX
            case 'D':
                return AreaType.LEOPARD
            case _:
                return AreaType.DRAGON

    def get_enemy_click(self):
        area, num = self.value.split('-')
        match num:
            case '1':
                return AbyssShadowsAssets.C_BOSS_CLICK_AREA
            case '2':
                return AbyssShadowsAssets.C_GENERAL_1_CLICK_AREA
            case '3':
                return AbyssShadowsAssets.C_GENERAL_2_CLICK_AREA
            case '4':
                return AbyssShadowsAssets.C_ELITE_1_CLICK_AREA
            case '5':
                return AbyssShadowsAssets.C_ELITE_2_CLICK_AREA
            case '6':
                return AbyssShadowsAssets.C_ELITE_3_CLICK_AREA
            case _:
                return AbyssShadowsAssets.C_ELITE_1_CLICK_AREA

    def get_enemy_type(self):
        area, num = self.value.split('-')
        match num:
            case '1':
                return EnemyType.BOSS
            case '2':
                return EnemyType.GENERAL
            case '3':
                return EnemyType.GENERAL
            case '4':
                return EnemyType.ELITE
            case '5':
                return EnemyType.ELITE
            case '6':
                return EnemyType.ELITE
            case _:
                return EnemyType.ELITE


class CodeList(list[Code]):

    def __init__(self, v: str):
        def expand_str(v: str):
            if v.find('-') != -1:
                return [v]
            if v in ['A', 'B', 'C', 'D']:
                return [f'{v}-4', f'{v}-5', f'{v}-6', f'{v}-2', f'{v}-3', f'{v}-1']
            if v in ['1', '2', '3', '4', '5', '6']:
                return [f'A-{v}', f'B-{v}', f'C-{v}', f'D-{v}']

        def parse_order(value: str = None) -> list:
            if value == '':
                return []
            item_or_list = value.split(';')
            for src in item_or_list:
                for result in expand_str(src):
                    yield Code(result)

        super().__init__(parse_order(v))

    def save_to_obj(self, config_obj: str):
        ret = ""
        for item in self:
            ret += ';'
            ret += item.value
        ret = ret[1:]
        config_obj = ret


class Condition:
    # _is_time_out: bool = False
    _time = -1
    _timer: Timer = None
    # _is_damage_enough: bool = False
    _damage_max: int = -1

    _dont_need_check: bool = False

    # 存储结果,用于后期查询
    _condition_result: bool = False

    def __init__(self, value: str):
        # 为True时,相当于没有策略(所有情况都通过条件检查)
        if value == "TRUE":
            self._dont_need_check = True
        elif value == "FALSE":
            # 任何情况都不通过条件检查
            self._dont_need_check = False
        elif len(value) <= 3:
            # 3位数 当作时间
            try:
                self._time = int(value)
            except ValueError:
                self._time = 180
            self._timer = Timer(self._time)
        else:
            try:
                _damage = int(value)
            except ValueError:
                self._damage_max = 999999999

    #  检查条件
    def is_valid(self, damage: int = None):

        if self._time >= 0:
            if not self._timer.started():
                self._timer.start()
            if self._timer.started() and self._timer.reached():
                self._condition_result = True
                return True
        if self._damage_max >= 0 and damage is not None:
            if self._damage_max < damage:
                self._condition_result = True
                return True
        if self._dont_need_check:
            self._condition_result = True
            return True
        return False

    def is_need_damage_value(self):
        return self._damage_max >= 0

    def is_passed(self):
        return self._condition_result


class AbyssShadowsTime(ConfigBase):
    # 自定义运行时间
    custom_run_time_friday: Time = Field(default=Time(hour=19, minute=0, second=0))
    custom_run_time_saturday: Time = Field(default=Time(hour=19, minute=0, second=0))
    custom_run_time_sunday: Time = Field(default=Time(hour=19, minute=0, second=0))
    # 尝试主动开启狭间-区别于游戏中的自动开启狭间功能
    try_start_abyss_shadows: bool = Field(default=False, description='try_start_abyss_shadows_help')
    # 难度
    difficulty: AbyssShadowsDifficulty = Field(default=AbyssShadowsDifficulty.EASY, description='difficulty_help')


class ProcessManage(ConfigBase):
    # 攻击顺序 A,B,C,D 分别表示四个区域，123456表示区域内6个怪物，从上到下，从左到右的顺序
    #           1
    #       2       3
    #   4       5       6
    # 之间用-分隔，不同怪物用;分隔
    # 小蛇使用E,-后面表示打几只,例如E-2表示打两只小蛇
    # 例如 A-1;B-2;C-3...
    attack_order: str = Field(default='', description='attack_order_help')
    # 标记主怪
    # EnemyType,  多个用;分隔
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

    def is_need_mark_main(self, enemy_type):
        return str(enemy_type) in self.mark_main

    def parse_strategy(self, strategy: str):
        if strategy is None or strategy == '':
            return False
        return Condition(strategy)


class SavedParams(ConfigBase):
    # 已完成
    done: str = Field(default='', description='done_help')
    # 失败
    fail: str = Field(default='', description='fail_help')
    # 已知的已经打完的
    unavailable: str = Field(default='', description='unavailable_help')
    # 当前时间，用于判断存储参数有效性
    save_time: str = Field(default='2023-01-01', description='today_help')

    # def save(self):
    #     self.today = datetime.today().strftime('yyyy-mm-dd')
    #     self.config.save()

    def push_to(self, item, l):
        if len(l) > 0:
            l += ';'
        l += item


class AbyssShadows(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    abyss_shadows_time: AbyssShadowsTime = Field(default_factory=AbyssShadowsTime)
    process_manage: ProcessManage = Field(default_factory=ProcessManage)
    saved_params: SavedParams = Field(default_factory=SavedParams)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
