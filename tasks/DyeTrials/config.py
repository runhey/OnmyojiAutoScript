# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import Field

from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler


class DyeTrials(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)