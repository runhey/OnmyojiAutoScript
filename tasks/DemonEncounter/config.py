# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum, IntEnum
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, TimeDelta, dynamic_hide


class BossType(IntEnum):
    kiryou_utahime = 0  # 鬼灵歌姬
    shinkirou = 1  # 蜃气楼
    tsuchigumo = 2  # 土蜘蛛
    gashadokuro = 3  # 荒骷髅
    namazu = 4  # 地震鲶
    oboroguruma = 5  # 胧车
    nightly_aramitama = 6  # 夜荒魂


# 宝箱购买项目
class BoxBuyConfig(BaseModel):
    # 默认购买蓝票，未添加选项，没人会不买吧！
    box_buy_sushi: bool = Field(default=False, description='逢魔宝箱是否购买体力')


class BestDemonBossSelect(BaseModel):
    best_demon_kiryou_utahime_select: bool = Field(title='Best Kiryou Utahime Select', default=False, description='极鬼灵歌姬是否开启')
    best_demon_shinkirou_select: bool = Field(title='Best Shinkirou Select', default=False, description='极蜃气楼是否开启')
    best_demon_tsuchigumo_select: bool = Field(title='Best Tsuchigumo Select', default=False, description='极土蜘蛛是否开启')
    best_demon_gashadokuro_select: bool = Field(title='Best Gashadokuro Select', default=False, description='极荒骷髅是否开启')
    best_demon_namazu_select: bool = Field(title='Best Namazu Select', default=False, description='极地震鲇是否开启')
    best_demon_oboroguruma_select: bool = Field(title='Best Oboroguruma Select', default=False, description='极胧车是否开启')
    best_demon_nightly_aramitama_select: bool = Field(title='Best Nightly Aramitama Select', default=False, description='极夜荒魂是否开启')

    hide_fields = dynamic_hide('best_demon_kiryou_utahime_select', 'best_demon_oboroguruma_select',
                               'best_demon_nightly_aramitama_select')


# 不同封魔boss的御魂配置
class DemonConfig(BaseModel):
    enable: bool = Field(
        default=False,
        description="通过预设名称来匹配普通封魔御魂分组\n例如=> 逢魔之时,歌(中间的是英文逗号)",
    )
    # 周一
    demon_kiryou_utahime: str = Field(default="group,team", description="鬼灵歌姬御魂1")
    demon_kiryou_utahime_supplementary: str = Field(default="group,team", description="鬼灵歌姬御魂补充")
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
    best_demon_kiryou_utahime: str = Field(default="group,team", description="极鬼灵歌姬御魂1")
    best_demon_kiryou_utahime_supplementary: str = Field(default="group,team", description="极鬼灵歌姬御魂补充")
    best_demon_shinkirou: str = Field(default="group,team", description="极蜃气楼御魂")
    best_demon_tsuchigumo: str = Field(default="group,team", description="极土蜘蛛御魂")
    best_demon_gashadokuro: str = Field(default="group,team", description="极荒骷髅御魂")
    best_demon_namazu: str = Field(default="group,team", description="极地震鲇御魂")
    best_demon_oboroguruma: str = Field(default="group,team", description="极胧车御魂")
    best_demon_nightly_aramitamau: str = Field(default="group,team", description="极夜荒魂御魂")

    hide_fields = dynamic_hide('best_demon_kiryou_utahime', 'best_demon_kiryou_utahime_supplementary',
                               'best_demon_oboroguruma', 'best_demon_nightly_aramitamau')


def convert_to_general_battle_config(boss_type: str, demon_battle_conf: 'DemonBattleConfig' = None,
                                     best_demon_battle_conf: 'BestDemonBattleConfig' = None) -> GeneralBattleConfig:
    if demon_battle_conf:
        enable = getattr(demon_battle_conf, f'{boss_type}_enable', False)
        group, team = getattr(demon_battle_conf, boss_type, '1,1').split(',')
    elif best_demon_battle_conf:
        enable = getattr(best_demon_battle_conf, f'{boss_type}_enable', False)
        group, team = getattr(best_demon_battle_conf, boss_type, '1,1').split(',')
    else:
        enable = False
        group, team = (1, 1)
    return GeneralBattleConfig(preset_enable=enable, preset_group=group if enable else 1, preset_team=team if enable else 1)


class DemonBattleConfig(BaseModel):
    demon_shinkirou_enable: bool = Field(default=False, description='是否切换蜃气楼预设')
    demon_shinkirou: str = Field(default="-1,-1", description="蜃气楼预设")
    demon_tsuchigumo_enable: bool = Field(default=False, description='是否切换土蜘蛛预设')
    demon_tsuchigumo: str = Field(default="-1,-1", description="土蜘蛛预设")
    demon_gashadokuro_enable: bool = Field(default=False, description='是否切换荒骷髅预设')
    demon_gashadokuro: str = Field(default="-1,-1", description="荒骷髅预设")
    demon_namazu_enable: bool = Field(default=False, description='是否切换地震鲶预设')
    demon_namazu: str = Field(default="-1,-1", description="地震鲶预设")
    demon_oboroguruma_enable: bool = Field(default=False, description='是否切换胧车预设')
    demon_oboroguruma: str = Field(default="-1,-1", description="胧车预设")
    demon_nightly_aramitama_enable: bool = Field(default=False, description='是否切换夜荒魂预设')
    demon_nightly_aramitama: str = Field(default="-1,-1", description="夜荒魂预设")


class BestDemonBattleConfig(BaseModel):
    best_demon_shinkirou_enable: bool = Field(default=False, description='是否切换极蜃气楼预设')
    best_demon_shinkirou: str = Field(default="-1,-1", description="极蜃气楼预设")
    best_demon_tsuchigumo_enable: bool = Field(default=False, description='是否切换极土蜘蛛预设')
    best_demon_tsuchigumo: str = Field(default="-1,-1", description="极土蜘蛛预设")
    best_demon_gashadokuro_enable: bool = Field(default=False, description='是否切换极荒骷髅预设')
    best_demon_gashadokuro: str = Field(default="-1,-1", description="极荒骷髅预设")
    best_demon_namazu_enable: bool = Field(default=False, description='是否切换极地震鲶预设')
    best_demon_namazu: str = Field(default="-1,-1", description="极地震鲶预设")
    best_demon_oboroguruma_enable: bool = Field(default=False, description='是否切换极胧车预设')
    best_demon_oboroguruma: str = Field(default="-1,-1", description="极胧车预设")
    best_demon_nightly_aramitama_enable: bool = Field(default=False, description='是否切换极夜荒魂预设')
    best_demon_nightly_aramitamau: str = Field(default="-1,-1", description="极夜荒魂预设")

    hide_fields = dynamic_hide('best_demon_oboroguruma_enable', 'best_demon_oboroguruma',
                               'best_demon_nightly_aramitama_enable', 'best_demon_nightly_aramitamau')


class UtilizeScheduler(Scheduler):
    priority: int = Field(default=2, description='priority_help')


class DemonEncounter(ConfigBase):
    scheduler: UtilizeScheduler = Field(default_factory=UtilizeScheduler)
    box_buy_config: BoxBuyConfig = Field(default_factory=BoxBuyConfig)
    best_demon_boss_config: BestDemonBossSelect = Field(default_factory=BestDemonBossSelect)
    demon_soul_config: DemonConfig = Field(default_factory=DemonConfig)
    best_demon_soul_config: BestDemonConfig = Field(default_factory=BestDemonConfig)
    demon_battle_config: DemonBattleConfig = Field(default_factory=DemonBattleConfig)
    best_demon_battle_config: BestDemonBattleConfig = Field(default_factory=BestDemonBattleConfig)
