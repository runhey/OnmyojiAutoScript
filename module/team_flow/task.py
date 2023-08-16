# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import datetime, time
from random import randint


from module.config.config import Config


class Task:
    def __init__(self,
                 next_run: datetime,
                 limit_time: time,
                 target_run: datetime = None,
                 team_task: bool = False,
                 role: str = 'leader',
                 limit_count: int = 0,
                 ):
        self.next_run = next_run
        self.target_run = target_run
        self.limit_time = limit_time
        self.team_task = team_task
        self.role = role
        self.limit_count = limit_count







