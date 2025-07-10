# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, TimeDelta
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Utils.config_enum import ShikigamiClass

# 宝箱购买项目
class BoxBuyConfig(BaseModel):
    # 默认购买蓝票，未添加选项，没人会不买吧！
    box_buy_sushi: bool = Field(default=False, description='逢魔宝箱是否购买体力')

class BestDemonBossSelect(BaseModel):
    enable: bool = Field(
        default=False,
        description="是否开启极封魔",
    )
    best_demon_kiryou_select: bool = Field(title='Best Kiryou Select', default=False, description='极鬼灵歌姬是否开启')
    best_demon_shinkirou_select: bool = Field(title='Best Shinkirou Select', default=False, description='极蜃气楼是否开启')
    best_demon_tsuchigumo_select: bool = Field(title='Best Tsuchigumo Select', default=False, description='极土蜘蛛是否开启')
    best_demon_gashadokuro_select: bool = Field(title='Best Gashadokuro Select', default=False, description='极荒骷髅是否开启')
    best_demon_namazu_select: bool = Field(title='Best Namazu Select', default=False, description='极地震鲇是否开启')

# 不同封魔boss的御魂配置
class DemonConfig(BaseModel):
    enable: bool = Field(
        default=False,
        description="通过预设名称来匹配普通封魔御魂分组\n例如=> 逢魔之时,歌(中间的是英文逗号)",
    )
    # 周一
    demon_kiryou_utahime: str = Field(default="group,team", description="鬼灵歌姬御魂1")
    demon_kiryou_utahime_supplementary: str = Field(
        default="group,team", description="鬼灵歌姬御魂补充"
    )
    # 周二
    demon_shinkirou: str = Field(default="group,team", description="蜃气楼御魂")
    # 周三 土蜘蛛
    demon_tsuchigumo: str = Field(default="group,team", description="土蜘蛛御魂")
    # 周四 荒骷髅
    demon_gashadokuro: str = Field(default="group,team", description="荒骷髅御魂")
    # 周五 地震鲇
    demon_namazu: str = Field(default="group,team", description="地震鲇御魂")
    # 周六 胧车
    demon_oboroguruma: str = Field(default="group,team", description="胧车御魂")
    # 周日 夜荒魂
    demon_nightly_aramitama: str = Field(default="group,team", description="夜荒魂御魂")

# 不同极封魔boss的御魂配置
class BestDemonConfig(BaseModel):
    enable: bool = Field(
        default=False,
        description="通过预设名称来匹配极封魔御魂分组\n例如=> 逢魔之时,歌(中间的是英文逗号)",
    )
    # 周一 鬼灵歌姬
    best_demon_kiryou_utahime: str = Field(default="group,team", description="极鬼灵歌姬御魂1")
    best_demon_kiryou_utahime_supplementary: str = Field(
        default="group,team", description="极鬼灵歌姬御魂补充"
    )
    # 周二 极蜃气楼
    best_demon_shinkirou: str = Field(default="group,team", description="极蜃气楼御魂")
    # 周三 极土蜘蛛
    best_demon_tsuchigumo: str = Field(default="group,team", description="极土蜘蛛御魂")
    # 周四 极荒骷髅
    best_demon_gashadokuro: str = Field(default="group,team", description="极荒骷髅御魂")
    # 周五 极地震鲇
    best_demon_namazu: str = Field(default="group,team", description="极地震鲇御魂")

class UtilizeScheduler(Scheduler):
    priority: int = Field(default=2, description='priority_help')

class DemonEncounter(ConfigBase):
    scheduler: UtilizeScheduler = Field(default_factory=UtilizeScheduler)
    box_buy_config: BoxBuyConfig = Field(default_factory=BoxBuyConfig)
    best_demon_boss_config: BestDemonBossSelect = Field(default_factory=BestDemonBossSelect)
    demon_soul_config: DemonConfig = Field(default_factory=DemonConfig)
    best_demon_soul_config: BestDemonConfig = Field(default_factory=BestDemonConfig)
