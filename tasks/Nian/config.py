# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase

class NianConfig(BaseModel):
    buff_gold_50_click: bool = Field(default=False)
    buff_gold_100_click: bool = Field(default=False)


class Nian(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    nian_config: NianConfig = Field(default_factory=NianConfig)

