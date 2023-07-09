# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from pydantic import BaseModel, ValidationError, validator, Field

from module.logger import logger

class WhenTaskQueueEmpty(str, Enum):
    GOTO_MAIN = 'goto_main'
    GOTO_HOME = 'goto_home'
    CLOSE_GAME = 'close_game'

class Optimization(BaseModel):
    screenshot_interval: float = Field(default=0.3,
                                       description='screenshot_interval_help')
    combat_screenshot_interval: float = Field(default=1.0,
                                              description='combat_screenshot_interval_help')
    task_hoarding_duration: float = Field(default=0,
                                          description='task_hoarding_duration_help')
    when_task_queue_empty: WhenTaskQueueEmpty = Field(default=WhenTaskQueueEmpty.GOTO_MAIN,
                                                      description='when_task_queue_empty_help')

