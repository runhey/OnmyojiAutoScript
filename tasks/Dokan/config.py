# This Python file uses the following encoding: utf-8
# @brief    Configurations for Ryou Dokan Toppa (阴阳竂道馆突破配置)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas
import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler


class AttackDokanMasterType(str, Enum):
    """
        NOTE: 如果第一个道馆没有放弃突破,那么没有第二次选择道馆的机会
            目前如果设置打一次馆主,如果打不过(失败),会一直等待->挑战循环
            导致失去放弃突破的机会->无法进行第二次道馆
    """
    # 不打馆主                                  0
    ATTACK_ZERO_ZERO = "ATTACK_ZERO_ZERO"
    # 第二次攻击时攻击馆主一次                     1
    ATTACK_ZERO_ONE = "ATTACK_ZERO_ONE"
    # 第一次攻击时不攻击馆主,第二次攻击时攻击馆主一次     2
    ATTACK_ZERO_TWO = "ATTACK_ZERO_TWO"
    #                                           3
    ATTACK_ONE_ZERO = "ATTACK_ONE_ZERO"
    # 第一次攻击时攻击馆主一次,第二次攻击时攻击馆主一次 4
    ATTACK_ONE_ONE = "ATTACK_ONE_ONE"
    # 第一次攻击时攻击馆主一次,第二次攻击时攻击馆主二次 5
    ATTACK_ONE_TWO = "ATTACK_ONE_TWO"
    # 第一次攻击时攻击馆主二次, 没有第二次了          8
    ATTACK_TWO_TWO = "ATTACK_TWO_TWO"

    def __int__(self):
        match self.value:
            case "ATTACK_ZERO_ZERO":
                return 0
            case "ATTACK_ZERO_ONE":
                return 1
            case "ATTACK_ZERO_TWO":
                return 2
            case "ATTACK_ONE_ZERO":
                return 3
            case "ATTACK_ONE_ONE":
                return 4
            case "ATTACK_ONE_TWO":
                return 5
            case "ATTACK_TWO_TWO":
                return 8
            case _:
                return 8


class AttackAccountConfig(BaseModel):
    # 当天可攻击次数,用以记录当天运行历史,用作状态恢复,不用配置
    remain_attack_count: int = Field(default=2, description='remain_attack_count_help')
    # remain_attack_count 值记录的时间,不用配置
    attack_date: str = Field(default='2023-01-01', description='attack_date_help')
    # 每日最大攻击次数(1-2,默认2次),建议:僵尸寮配置2,其他寮配置1
    daily_attack_count: int = Field(default=2, description='daily_attack_count_help')
    # 攻击馆主配置,格式:ATTACK_X_Y          X:  第一个道馆,只打馆主一阵/两阵都打
    #                                    Y:  第二个道馆,只打馆主一阵/两阵都打
    # 建议普通寮配置ATTACK_TWO_TWO,僵尸寮看自己喜好
    attack_dokan_master: AttackDokanMasterType = Field(default=AttackDokanMasterType.ATTACK_TWO_TWO,
                                                       description='attack_dokan_master_help')

    def init_attack_count(self, callback=None):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.attack_date:
            self.attack_date = today
            self.remain_attack_count = 2
        if not callback:
            return
        callback()

    def attack_dokan_master_count(self) -> int:
        """
        根据当前配置,获取此次道馆突破,需要攻击馆主的次数
        @return: 当前突破,可攻击馆主的次数
        @rtype:
        """
        if self.attack_dokan_master == AttackDokanMasterType.ATTACK_ZERO_ZERO:
            return 0
        if self.attack_dokan_master == AttackDokanMasterType.ATTACK_TWO_TWO:
            return 2
        # 只攻击一次
        # 或者
        # 还有一次选择寮的机会,即,在打第一个寮的过程中
        if self.daily_attack_count == 1 or self.remain_attack_count >= 1:
            return int(self.attack_dokan_master) // 3
        # 攻击两次 且 在打第二个寮的过程中
        return int(self.attack_dokan_master) % 3

    def set_attack_count(self, count=2, callback=None):
        if count < 0:
            return
        self.attack_date = datetime.now().strftime("%Y-%m-%d")
        self.remain_attack_count = count
        if not callback:
            return
        callback()

    def del_attack_count(self, count, callback=None):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.attack_date:
            self.attack_date = today
            self.remain_attack_count = 2
        self.remain_attack_count -= count
        if not callback:
            return
        callback()


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
    anti_detect_click_fixed_random_area: bool = Field(default=False,
                                                      description='anti_detect_click_fixed_random_area_help')

    # 只在周一到周四开启道馆
    monday_to_thursday: bool = Field(default=True, description='monday_to_thursday_help')

    # 是否尝试开启道馆,在道馆未开启时,尝试查找合适道馆并开启,需要有权限
    try_start_dokan: bool = Field(default=False, description='try_start_dokan')

    # 道馆系数,赏金/人数 根据喜好配置
    find_dokan_score: float = Field(default=4.6, description='dokan_score_help')

    # 道馆最小人数限制
    min_people_num: int = Field(default=-1, description='min_people_num_help')

    # 最少赏金设置
    min_bounty: int = Field(default=0, description='min_bounty_help')

    # 单次查找道馆时,最大刷新次数.超过此次数后,若还未找到符合要求的,会随机选择一个道馆
    find_dokan_refresh_count: int = Field(default=7, description='find_dokan_refresh_count_help')

    # 是否切换阵容(速攻阵容/挂机阵容)
    switch_preset_enable: bool = Field(default=False, description='switch_preset_enable_help')

    # 速攻阵容 格式:n,n
    preset_group_1: str = Field(default="", description='preset_group_1_help')
    # 挂机阵容
    preset_group_2: str = Field(default="", description='preset_group_2_help')

    # 按式神名字绿标，多个名字用“,”分隔
    green_mark_shikigami_name: str = Field(default="", description='green_mark_shikigami_name_help')

    def parse_preset_group(self, value: str):
        re_str = r"([1-7])\,([1-5])"
        tmp = re.match(re_str, value)
        if not tmp:
            return None, None
        return int(tmp.group(1)), int(tmp.group(2))


class Dokan(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    dokan_config: DokanConfig = Field(default_factory=DokanConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    attack_count_config: AttackAccountConfig = Field(default_factory=AttackAccountConfig)
