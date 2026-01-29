# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum  # type: ignore
from datetime import datetime, time  # type: ignore
from pydantic import BaseModel, Field

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time, TimeDelta
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig


class Layer(str, Enum):
    YANWU: str = "鬼兵演武"
    MIJING: str = "兵藏秘境"
    CHUANCHENG: str = "传承试炼"
    MENGXU: str = "梦虚秘境"


class SkillMode(str, Enum):
    PVE = 'PVE'
    PVP = 'PVP'


class HeroTestConfig(BaseModel):
    # 副本选择
    layer: Layer = Field(
        default=Layer.YANWU,
        description="选择要打的关卡。\n兵藏秘境升级顺序八华斩->无畏 -> 暴击伤害 -> 默认祝福 -> 默认属性\n"
                    "藤原道长矩阵博士攻略:https://www.bilibili.com/opus/1162129635334422531",
    )
    skill_mode: SkillMode = Field(default=SkillMode.PVE, description="技能本技能偏向\n藤原道长使用攻略高配阵容,需自己配置好技能和祝福")
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description="limit_time_help")
    # 限制次数
    limit_count: int = Field(default=100, description="limit_count_help")
    # 是否开启经验加成
    exp_50_buff_enable_help: bool = Field(default=False, description="打开经验50%加成")
    exp_100_buff_enable_help: bool = Field(
        default=False, description="打开经验100%加成"
    )


class HeroTest(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    herotest: HeroTestConfig = Field(default_factory=HeroTestConfig)
    general_battle: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)