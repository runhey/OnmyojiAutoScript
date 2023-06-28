# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, ValidationError, validator, Field

from module.logger import logger


class Error(BaseModel):
    handle_error: bool = Field(default=True,
                               description='handle_error_help')
    save_error: bool = Field(default=True,
                             description='')
    screenshot_length: int = Field(default=1,
                                   description='')


