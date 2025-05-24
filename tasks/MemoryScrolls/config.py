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

class ScrollNumber(str, Enum):
    SCROLL_1 = "卷一"
    SCROLL_2 = "卷二"
    SCROLL_3 = "卷三"
    SCROLL_4 = "卷四"
    SCROLL_5 = "卷五"
    SCROLL_6 = "卷六"

class MemoryScrollsConfig(ConfigBase):
    scroll_number: ScrollNumber = Field(default=ScrollNumber.SCROLL_1, description='scroll_number_help')

class MemoryScrolls(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    memory_scrolls_config: MemoryScrollsConfig = Field(default_factory=MemoryScrollsConfig)

