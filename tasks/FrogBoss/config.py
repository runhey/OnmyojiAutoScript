# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from enum import Enum
from pydantic import BaseModel, Field

from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.config_scheduler import Scheduler


class Strategy(str, Enum):
    Majority = 'frog_majority'
    Minority = 'frog_minority'
    Bilibili = 'frog_bilibili'
    Dashen = 'frog_dashen'
    DashenSpecific = 'frog_dashen_specific'
    AlwaysRed = 'frog_always_red'
    AlwaysBlue = 'frog_always_blue'

# 内置大神博主池（昵称, hex uid）。uid = 博主主页网址 ds.163.com/user/<uid> 里那串
DASHEN_BUILTIN_UPS = [
    ("面灵气喵", "462382f1127b46c5add1185d88f0ea40"),
    ("余岁岁", "54399446d5084a0e8878dac8f6ff56d0"),
    ("七面相", "840742d60e4a43208605ae68ca8c3f64"),
    ("待机中的徐ok", "c3c989fae4074d04b478b8ba47ae4120"),
    ("雯雯", "aaa923436aa440df9ac1ee3f47387b99"),
    ("晨时微凉", "72584a679e2f45b6859566b5523400d5"),
    ("梅布斯尼", "3d4726d99f2642a485729695b798cb8c"),
    ("鸽海成路", "1d2dcbbd7e3d481c8d0f27ba4ff0dc71"),
    ("徐清林", "21657a558bdd4ddfb6501298350336e7"),
    ("不包邮哦亲", "0e4e0c5a1e494a1fa9a58ac55de689c1"),
    ("天真珈百璃", "30e383c884f844a18a7a76fe3c1e888f"),
    ("薛定谔家查查尔", "d9dc2a75497c4a91b2db1e909a36544d"),
    ("嘤嘤井", "e7107cd3010e418da26672669d8eeb5e"),
    ("Prince班崎", "74adeb1bfb2b4cf382edbbb430da2149"),
    ("靠脸混饭", "e87f855f36f24b34b9d8f8a4fb2d62b2"),
    ("夜神月丶L", "82de68c7672e4b6da65493fb829b57b6"),
    ("是大荣啦", "f6d6bb15d6024200a985752e2ab4c373"),
    ("炒饭菌", "06e2bba14a914012bc8064601cfa19ea"),
    ("清流不加班", "8982241de1844638b4bb455139b8dcc0"),
    ("槐夏三十", "a9724e98c1cb4a4e931ebc3f467ea73d"),
    ("落沫颜", "e9b0a16325af46628e8dfb9e7942cf1d"),
    ("Mico林木森", "b6b5bc8277e34f69aeca018db0081397"),
    ("CC南浔", "74db771d92a54c28ae3e98d19aa565a3"),
    ("冰七喜Den", "e498e524252041e29999b38e57c4df1d"),
    ("行水姑娘", "30b0c2923faa483f95572c324a5bc910"),
    ("更慕林", "e32aedbdd8da46a5b5b497a16c4b7658"),
]
# 配置框默认值：内置池直接写出来，使用者可自由增删改（每行 昵称,uid）
DASHEN_POOL_DEFAULT = '\n'.join(f'{n},{u}' for n, u in DASHEN_BUILTIN_UPS)


class FrogBossConfig(ConfigBase):
    before_end_frog: Time = Field(default=Time(0, 15, 0), description='before_end_frog_help')
    strategy_frog: Strategy = Field(default=Strategy.Dashen, description='strategy_frog_help')
    frog_gold_preset: int = Field(default=5, description='frog_gold_preset_help')
    dashen_uid: str = Field(default='', description='dashen_uid_help')
    dashen_pool: str = Field(default=DASHEN_POOL_DEFAULT, description='dashen_pool_help')

class FrogBoss(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    frog_boss_config: FrogBossConfig = Field(default_factory=FrogBossConfig)
