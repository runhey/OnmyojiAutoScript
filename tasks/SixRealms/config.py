# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig

# class SixRealmsGate(BaseModel):
#     # 还没想好
#     greed_maneki: bool = Field(default=False, description="greed_maneki_help")


class SixRealms(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    # six_realms_gate: SixRealmsGate = Field(default_factory=SixRealmsGate)













