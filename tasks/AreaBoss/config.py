# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.config_scheduler import Scheduler
from tasks.AreaBoss.config_boss import Boss


class AreaBoss(BaseModel):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    general_battle: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)
    boss: Boss = Field(default_factory=Boss)
