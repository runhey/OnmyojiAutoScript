# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase

class QuizConfig(ConfigBase):
    # 打多少轮
    quiz_cnt: int = Field(default=1, description='quiz_cnt_help')
    # 每轮多少道题
    quiz_per_round: int = Field(default=150, description='quiz_per_round_help')

class Quiz(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    quiz_config: QuizConfig = Field(default_factory=QuizConfig)
