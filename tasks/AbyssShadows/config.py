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
        return ';'.join(item.value for item in self)


class Condition:
    """
    Condition类用于管理一个条件对象，该对象可以基于时间或伤害值来判断条件是否满足。
    它支持立即满足条件、基于时间满足条件和基于伤害值满足条件三种方式。
    """

    def __init__(self, value: str):
        """
        初始化Condition对象。

        参数:
        value (str): 用于设置条件的字符串值，可以是'TRUE', 'FALSE', 时间（秒），或最大伤害值。
        """
        # True 立即退出
        # False     任何情况下,该条件检查不通过
        self._dont_need_check: bool = False
        # 时间,单位秒.时间到达时,条件满足
        # Note 在对象生成时，_timer 即开始运行
        self._time = -1
        self._timer: Timer = None
        # 最大伤害,伤害达到该数值时,条件满足
        self._damage_max: int = -1
        # 存储结果,用于后期查询
        self._condition_result: bool = False

        # 根据输入值设置条件
        if value.upper() == "TRUE":
            # 为True时,相当于没有策略(所有情况都通过条件检查)
            self._dont_need_check = True
        elif value.upper() == "FALSE":
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

    def is_valid(self, damage: int = None):
        """
        检查当前条件是否满足。

        参数:
        damage (int, 可选): 当前的伤害值。默认为None。

        返回:
        bool: 如果条件满足则返回True，否则返回False。
        """
        # 检查时间条件
        if self._time >= 0:
            # if not self._timer.started():
            #     self._timer.start()
            if self._timer.started() and self._timer.reached():
                self._condition_result = True
                return True
        # 检查伤害条件
        if self._damage_max >= 0 and damage is not None:
            if self._damage_max < damage:
                self._condition_result = True
                return True
        # 检查是否无需检查条件
        if self._dont_need_check:
            self._condition_result = True
            return True
        # 如果以上条件都不满足
        self._condition_result = False
        return False

    def is_need_damage_value(self):
        """
        检查是否需要伤害值来判断条件。

        返回:
        bool: 如果需要伤害值则返回True，否则返回False。
        """
        return self._damage_max >= 0

    def is_passed(self):
        """
        检查条件是否已满足。

        返回:
        bool: 如果条件已满足则返回True，否则返回False。
        """
        return self._condition_result

    def __repr__(self):
        """
        返回Condition对象的字符串表示。

        返回:
        str: Condition对象的字符串表示。
        """
        return f"Condition(time={self._time},damage_max={self._damage_max},dont_need_check={self._dont_need_check})"


class AbyssShadowsTime(ConfigBase):
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
    # 未实现-->小蛇使用E,-后面表示打几只,例如E-2表示打两只小蛇
    # 例如 A-1;B-2;C-3...
    attack_order: str = Field(default='A-1;B-1;B;A-2;A-3;A-4;A-5;A-6', description='attack_order_help')
    # 标记主怪
    # EnemyType,  多个用;分隔
    mark_main: MarkMainConfig = Field(default=MarkMainConfig.BOSS_ONLY, description='mark_main_help')
    # 是否启用切换御魂
    enable_switch_soul_in_as: bool = Field(default=False, description='enable_switch_soul_in_as_help')
    # 首领预设
    preset_boss: str = Field(default='6,1', description='preset_boss_help')
    # 副将预设
    preset_general: str = Field(default='6,2', description='preset_general_help')
    # 精英预设
    preset_elite: str = Field(default='6,3', description='preset_elite_help')
    # 小蛇预设
    # preset_snake: str = Field(default='', description='preset_snake_help')
    # 首领策略 等待打完/时间到了退出/伤害足够退出/秒退
    # 可用值: 'TRUE', 'FALSE', 时间（秒），或最大伤害值
    # 详见类 {Condition}
    strategy_boss: str = Field(default='FALSE', description='strategy_boss_help')
    # 副将策略
    strategy_general: str = Field(default='30', description='strategy_general_help')
    # 精英策略
    strategy_elite: str = Field(default='4380000', description='strategy_elite_help')

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

    def generate_quit_condition(self, enemy_type: EnemyType):
        strategy = None
        match enemy_type:
            case EnemyType.BOSS:
                strategy = self.strategy_boss
            case EnemyType.ELITE:
                strategy = self.strategy_elite
            case EnemyType.GENERAL:
                strategy = self.strategy_general
        if strategy is None or strategy == '':
            return False
        return Condition(strategy)


class SavedParams(ConfigBase):
    # 参数保存的时间,用于判断是不是当天的数据
    save_date: str = Field(default='', description='save_date_help')
    # 已完成
    done: str = Field(default='', description='done_help')
    # 已知的已经打完的
    unavailable: str = Field(default='', description='unavailable_help')


class AbyssShadows(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    abyss_shadows_time: AbyssShadowsTime = Field(default_factory=AbyssShadowsTime)
    process_manage: ProcessManage = Field(default_factory=ProcessManage)
    saved_params: SavedParams = Field(default_factory=SavedParams)
    # general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    # switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
