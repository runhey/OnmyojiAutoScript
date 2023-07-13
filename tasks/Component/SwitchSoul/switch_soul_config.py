# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, time



class SwitchSoulConfig(BaseModel):
    enable: bool = Field(default=False)
    switch_group_team: str = Field(default='-1,-1', description='switch_group_team_help')

