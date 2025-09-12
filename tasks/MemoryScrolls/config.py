# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import timedelta
from pydantic import BaseModel, Field
from enum import Enum
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time

class DoubleScrolls(str, Enum):
    ONE = "默认绘卷一"
    TWO = "双绘卷之二"

class ScrollNumber(str, Enum):
    ONE = "卷一"
    TWO = "卷二"
    THREE = "卷三"
    FOUR = "卷四"
    FIVE = "卷五"
    SIX = "卷六"

class MemoryScrollsConfig(ConfigBase):
    auto_contribute_memoryscrolls: bool = Field(default=True, description='自动贡献绘卷碎片')
    double_scrolls: DoubleScrolls = Field(default=DoubleScrolls.ONE, description='double_scrolls_help')
    scroll_number: ScrollNumber = Field(default=ScrollNumber.ONE, description='scroll_number_help')
    auto_close_exploration: bool = Field(default=False, description='指定绘卷结束后，自动关闭探索任务，避免长时间无意义执行')
    notification_95: bool = Field(default=False, description='到达95%进度时发送通知')

class MemoryScrollsFinish(ConfigBase):
    auto_finish_exploration: bool = Field(default=False, description='小绘卷满50后自动结束当日探索任务')
    # 当日小绘卷满50后指定下次运行时间
    next_exploration_time: Time = Field(default=Time(hour=7, minute=0, second=0))

class MemoryScrolls(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    memory_scrolls_config: MemoryScrollsConfig = Field(default_factory=MemoryScrollsConfig)
    memory_scrolls_finish: MemoryScrollsFinish = Field(default_factory=MemoryScrollsFinish)

