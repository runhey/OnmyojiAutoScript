# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Sougenbi.config_scheduler import Scheduler


class Sougenbi(BaseModel):
    scheduler: Scheduler = Field(default_factory=Scheduler)

