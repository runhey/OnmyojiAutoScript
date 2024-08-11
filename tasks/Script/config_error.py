# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, ValidationError, validator, Field
from tasks.Component.config_base import MultiLine

from module.logger import logger


class Error(BaseModel):
    handle_error: bool = Field(default=True,
                               description='handle_error_help')
    save_error: bool = Field(default=True,
                             description='')
    screenshot_length: int = Field(default=1,
                                   description='')
    notify_enable: bool = Field(default=False,
                                description='')
    notify_config: MultiLine = Field(default='provider: null', description='notify_config_help')


