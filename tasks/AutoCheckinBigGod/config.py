# This Python file uses the following encoding: utf-8
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, MultiLine


class CheckinBigGodConfig(BaseModel):
    usage: MultiLine = Field(
        title='Usage',
        default='',
        description='checkin_big_god_usage_help'
    )


class AutoCheckinBigGod(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    checkin_config: CheckinBigGodConfig = Field(default_factory=CheckinBigGodConfig)
