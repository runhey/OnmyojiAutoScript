# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from pydantic import BaseModel, ValidationError, validator, Field

from module.logger import logger

class WhenTaskQueueEmpty(str, Enum):
    GOTO_HOME = 'goto_home'
    CLOSE_GAME = 'close_game'

class Optimization(BaseModel):
    screenshot_interval: float = Field(default=0.3,
                                       description='none')
    combat_screenshot_interval: float = Field(default=1.0,
                                              description='none')
    task_hoarding_duration: float = Field(default=0,
                                          description='none')
    when_task_queue_empty: WhenTaskQueueEmpty = Field(default=WhenTaskQueueEmpty.GOTO_HOME,
                                                      description='you can select goto home where nothing to do')