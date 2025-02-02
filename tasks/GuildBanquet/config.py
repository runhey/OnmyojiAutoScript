# This Python file uses the following encoding: utf-8
# @author ohspecial
# github https://github.com/ohspecial
from enum import Enum  

from pydantic import Field, BaseModel, SerializationInfo, field_serializer

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time, dynamic_hide


class Weekday(str,Enum):
    Monday: str = "星期一"
    Tuesday: str = "星期二" 
    Wednesday: str = "星期三"
    Thursday: str = "星期四"
    Friday: str = "星期五"
    Saturday: str = "星期六"
    Sunday: str = "星期日"

class GuildBanquetTime(BaseModel):
    # 自定义运行时间
    day_1: Weekday = Field(
        default=Weekday.Wednesday,
        description="每周第1次运行时间设置，注意第一次时间要比第二次时间早",
    )
    run_time_1: Time = Field(default=Time(hour=19, minute=0, second=0))
    day_2: Weekday = Field(
        default=Weekday.Saturday,
        description="每周第2次运行时间设置",
    )
    run_time_2: Time = Field(
        default=Time(hour=19, minute=0, second=0), 
        description="每周第2次运行时间设置"
    )

    hide_fileds = dynamic_hide('run_time_1', 'run_time_2')


class GuildBanquet(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    guild_banquet_time: GuildBanquetTime = Field(default_factory=GuildBanquetTime)

