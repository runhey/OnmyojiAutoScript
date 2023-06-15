# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field


class Emergency(BaseModel):
    accept_friend_invitation: bool = Field(default=True,
                                           description="default is true")
