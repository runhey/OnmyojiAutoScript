from pydantic import BaseModel, Field
from enum import Enum
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.config_scheduler import Scheduler



class RaidConfig(BaseModel):
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    # 限制次数
    limit_count: int = Field(default=50, description='limit_count_help')
    # 攻破完成后指定下次运行时间
    next_ryoutoppa_time: Time = Field(default=Time(hour=7, minute=0, second=0))
    # 是否跳过难度较高的结界，失败后不再攻打该结界
    skip_difficult: bool = Field(default=True, description='skip_difficult_help')
    # 寮管理开启寮突破
    ryou_access: bool = Field(default=False, description='ryou_access_help')
    # 正式进攻会设定 2s - 10s 的随机延迟，避免攻击间隔及其相近被检测为脚本。
    random_delay: bool = Field(default=False, description='random_delay_help')


    # raid_mode: RaidMode = Field(title='Raid Mode', default=RaidMode.ATTACK_ALL,
    #                             description='raid_mode_help')
    # attack_number: AttackNumber = Field(title='Attack Number', default=AttackNumber.ALL,
    #                                     description='')
    # 打完没票了 0/6 => 失败
    # 突破压根没开  +> 失败
    # 时间打满了  成功
    # 次数打满了  成功
    # 打完了（有失败的但是大不了） 成功



class RyouToppa(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    raid_config: RaidConfig = Field(default_factory=RaidConfig)
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)