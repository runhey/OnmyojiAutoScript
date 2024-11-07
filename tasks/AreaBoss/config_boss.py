# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field

class AreaBossFloor(str, Enum):
    ONE = '一星'
    TEN = '十星'
    DEFAULT = '不更改'

class Boss(BaseModel):
    boss_number: int = Field(title='Boss Number',
                             default=3,
                             description='默认为3 可选[1-3], 当你设置为三时默认你拥有全部的挑战资格，会挑战热门的前三个，\n'
                                         '如果不是请将你可以挑战的boss进行收藏',
                             ge=1, le=3)
    # 是否查找当日悬赏鬼王
    boss_reward: bool = Field(default=False, description='boss_reward_help')
    # 悬赏默认打较简单的一星鬼王，若想要更高悬赏奖励可自行更改为十星或不更改（保留已勾选DEBUFF）
    reward_floor: AreaBossFloor = Field(default=AreaBossFloor.ONE, description='reward_floor_help')
    # 是否使用收藏的
    use_collect: bool = Field(default=False, description='use_collect_help')
