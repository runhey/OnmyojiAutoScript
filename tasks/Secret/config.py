# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler as BaseScheduler
from tasks.Component.config_base import ConfigBase, TimeDelta
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig

class Scheduler(BaseScheduler):
    success_interval: TimeDelta = Field(default=TimeDelta(days=7), description='success_interval_help')
    failure_interval: TimeDelta = Field(default=TimeDelta(days=7), description='failure_interval_help')

class SecretConfig(BaseModel):
    secret_gold_50: bool = Field(title='Secret Gold 50', default=False, description='secret_gold_50_help')
    secret_gold_100: bool = Field(title='Secret Gold 100', default=False, description='secret_gold_100_help')
    layer_10: bool = Field(title='Layer 10', default=False, description='layer_10_help')
    layer_9: bool = Field(title='Layer 9', default=False)


class Secret(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    secret_config: SecretConfig = Field(default_factory=SecretConfig)
    general_battle: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)




