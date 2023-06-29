# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.GlobalGame.config_emergency import Emergency
from tasks.Component.config_base import ConfigBase

class GlobalGame(BaseModel):
    emergency: Emergency = Field(default_factory=Emergency)

