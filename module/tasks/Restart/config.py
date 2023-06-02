# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, ValidationError, validator, Field

from module.logger import logger
from module.tasks.Restart.config_scheduler import Scheduler

class Restart(BaseModel):
    scheduler: Scheduler = Field(default_factory=Scheduler)