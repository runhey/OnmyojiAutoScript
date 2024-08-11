# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase

class ExperienceYoukai(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)

