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


# 不同封魔boss的御魂配置
class DemonConfig(BaseModel):
    enable: bool = Field(
        default=False,
        description="通过预设名称来匹配御魂分组\n例如=> 逢魔之时,歌(中间的是英文逗号)",
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


class UtilizeScheduler(Scheduler):
    priority = Field(default=2, description='priority_help')

class DemonEncounter(ConfigBase):
    scheduler: UtilizeScheduler = Field(default_factory=UtilizeScheduler)
    demon_soul_config: DemonConfig = Field(default_factory=DemonConfig)
