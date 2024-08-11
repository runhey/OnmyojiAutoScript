# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from pydantic import BaseModel, ValidationError, validator, Field

from module.logger import logger

class WhenTaskQueueEmpty(str, Enum):
    GOTO_MAIN = 'goto_main'
    CLOSE_GAME = 'close_game'

class ScheduleRule(str, Enum):
    FILTER = 'Filter'  # 默认的基于过滤器，（按照开发者设定的调度规则进行调度）
    FIFO = 'FIFO'  # 先来后到，（按照任务的先后顺序进行调度）
    PRIORITY = 'Priority'  # 基于优先级，同一个优先级的任务按照先来后到的顺序进行调度，优先级高的任务先调度

class Optimization(BaseModel):
    screenshot_interval: float = Field(default=0.3,
                                       description='screenshot_interval_help')
    combat_screenshot_interval: float = Field(default=1.0,
                                              description='combat_screenshot_interval_help')
    task_hoarding_duration: float = Field(default=0,
                                          description='task_hoarding_duration_help')
    when_task_queue_empty: WhenTaskQueueEmpty = Field(default=WhenTaskQueueEmpty.GOTO_MAIN,
                                                      description='when_task_queue_empty_help')
    schedule_rule: ScheduleRule = Field(default=ScheduleRule.FILTER, description='schedule_rule_help')

