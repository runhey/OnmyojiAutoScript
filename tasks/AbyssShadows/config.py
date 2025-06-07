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


class ClickArea(Enum):
    """ 点击区域 """
    BOSS = AbyssShadowsAssets.C_BOSS_CLICK_AREA
    GENERAL_1 = AbyssShadowsAssets.C_GENERAL_1_CLICK_AREA
    GENERAL_2 = AbyssShadowsAssets.C_GENERAL_2_CLICK_AREA
    ELITE_1 = AbyssShadowsAssets.C_ELITE_1_CLICK_AREA
    ELITE_2 = AbyssShadowsAssets.C_ELITE_2_CLICK_AREA
    ELITE_3 = AbyssShadowsAssets.C_ELITE_3_CLICK_AREA


class IndexMap(str, Enum):
    """ 索引映射 """
    DRAGON = "A"  # 神龙暗域
    PEACOCK = "B"  # 孔雀暗域
    FOX = "C"  # 白藏主暗域
    LEOPARD = "D"  # 黑豹暗域
    BOSS = "1"  # BOSS
    GENERAL_1 = "2"  # 副将
    GENERAL_2 = "3"
    ELITE_1 = "4"  # 精英
    ELITE_2 = "5"
    ELITE_3 = "6"


class EnemyType(str, Enum):
    """ 敌人类型 """
    BOSS = "BOSS"  # 首领
    GENERAL = "GENERAL"  # 副将
    ELITE = "ELITE"  # 精英


class AbyssShadowsDifficulty(str, Enum):
    EASY = "EASY"
    NORMAL = "NORMAL"
    HARD = "HARD"


class MarkMainConfig(str, Enum):
    """ 标记主怪策略 """
    NONE = "NONE"  # 不需要标记
    BOSS_ONLY = "BOSS_ONLY"  # 仅标记首领
    GENERAL_ONLY = "GENERAL_ONLY"  # 仅标记副将
    ELITE_ONLY = "ELITE_ONLY"  # 仅标记精英怪

    BOSS_AND_GENERAL = "BOSS_AND_GENERAL"  # 标记首领和副将
    ELITE_AND_GENERAL = "ELITE_AND_GENERAL"  # 标记精英怪和副将
    ELITE_AND_BOSS = "ELITE_AND_BOSS"  # 标记精英怪和首领

    ALL = "ALL"  # 标记所有敌人


class Code(str):
    def __init__(self, value: str):
        self.value = value

    def get_areatype(self):
        area, num = self.value.split('-')

        area_name = ""
        for item in IndexMap:
            if item.value == area:
                area_name = item.name
                break

        return AreaType[area_name]

    def get_enemy_click(self) -> RuleClick:
        _, num = self.value.split('-')

        # 查找 IndexMap 中 value == num 的项
        for item in IndexMap:
            if item.value == num:
                try:
                    # 返回 ClickArea 中同名项
                    return ClickArea[item.name].value
                except KeyError:
                    break  # 没找到就走默认逻辑

        # 默认返回精英怪1的点击区域
        return ClickArea.ELITE_1.value

    def get_enemy_type(self):
        area, num = self.value.split('-')
        # 查找 IndexMap 中 value == num 的枚举项
        for item in IndexMap:
            if item.value == num:
                try:
                    return EnemyType[item.name.split("_")[0]]
                except KeyError:
                    return EnemyType.ELITE  # 默认值

        return EnemyType.ELITE  # 未找到时默认返回 ELITE


class CodeList(list[Code]):

    def __init__(self, v: str):
        def expand_str(v: str):
            if v.find('-') != -1:
                return [v]

            VALID_AREAS = [area.value for area in IndexMap if area.name in AreaType.__members__]
            VALID_NUMBERS = [str(i) for i in range(1, 7)]

            if v in VALID_AREAS:
                return [f'{v}-4', f'{v}-5', f'{v}-6', f'{v}-2', f'{v}-3', f'{v}-1']

            if v in VALID_NUMBERS:
                # areas = [area.value for area in IndexMap if area.name in AreaType.__members__]
                return [f'{area}-{v}' for area in VALID_AREAS]

            return []

        def parse_order(value: str = None) -> list:
            if value == '':
                return []
            item_or_list = value.split(';')
            for src in item_or_list:
                for result in expand_str(src):
                    yield Code(result)

        super().__init__(parse_order(v))

    def parse2str(self):
        ret = ""
        for item in self:
            ret += ';'
            ret += item.value
        return ret[1:]


class Condition:
    # _is_time_out: bool = False
    _time = -1
    _timer: Timer = None
    # _is_damage_enough: bool = False
    _damage_max: int = -1
    # True 立即退出
    # False     任何情况下,该条件检查不通过
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
            self._timer.start()
        else:
            try:
                self._damage_max = int(value)
            except ValueError:
                self._damage_max = 999999999

    #  检查条件
    def is_valid(self, damage: int = None):

        if self._time >= 0:
            # if not self._timer.started():
            #     self._timer.start()
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
        self._condition_result = False
        return False

    def is_need_damage_value(self):
        return self._damage_max >= 0

    def is_passed(self):
        return self._condition_result

    def __repr__(self):
        return f"Condition(time={self._time},damage_max={self._damage_max},dont_need_check={self._dont_need_check})"


class AbyssShadowsTime(ConfigBase):
    # 自定义运行时间
    custom_run_time_friday: Time = Field(default=Time(hour=19, minute=0, second=0))
    custom_run_time_saturday: Time = Field(default=Time(hour=19, minute=0, second=0))
    custom_run_time_sunday: Time = Field(default=Time(hour=19, minute=0, second=0))
    # 尝试主动开启狭间-区别于游戏中的自动开启狭间功能
    try_start_abyss_shadows: bool = Field(default=False, description='try_start_abyss_shadows_help')
    # 难度
    difficulty: AbyssShadowsDifficulty = Field(default=AbyssShadowsDifficulty.EASY, description='difficulty_help')
    # 是否尝试补全首领副将精英 2/4/6 数量限制
    try_complete_enemy_count: bool = Field(default=False, description='try_complete_enemy_count_help')


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
    mark_main: MarkMainConfig = Field(default=MarkMainConfig.BOSS_ONLY, description='mark_main_help')
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

    def is_need_mark_main(self, enemy_type: EnemyType) -> bool:
        strategy = self.mark_main  # 获取 MarkMainConfig 枚举值

        match strategy:
            case MarkMainConfig.BOSS_ONLY:
                return enemy_type == EnemyType.BOSS
            case MarkMainConfig.GENERAL_ONLY:
                return enemy_type == EnemyType.GENERAL
            case MarkMainConfig.ELITE_ONLY:
                return enemy_type == EnemyType.ELITE
            case MarkMainConfig.BOSS_AND_GENERAL:
                return enemy_type in (EnemyType.BOSS, EnemyType.GENERAL)
            case MarkMainConfig.ELITE_AND_GENERAL:
                return enemy_type in (EnemyType.ELITE, EnemyType.GENERAL)
            case MarkMainConfig.ELITE_AND_BOSS:
                return enemy_type in (EnemyType.ELITE, EnemyType.BOSS)
            case MarkMainConfig.ALL:
                return True
            case _:
                return False

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
