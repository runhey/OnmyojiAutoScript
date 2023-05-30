# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, ValidationError, validator, Field

from module.logger import logger


class Error(BaseModel):
    handle_error: bool = Field(default=False,
                               description='none')
    save_error: bool = Field(default=False,
                             description='none')
    screenshot_length: int = Field(default=1,
                                   description='The number of recent screenshots to save when something goes wrong')