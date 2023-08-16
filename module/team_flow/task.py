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

    def update_info(self,
                    next_run: datetime,
                    limit_time: time,
                    limit_count: int,
                    role: str):
        # next_run
        if isinstance(next_run, datetime):
            self.next_run = next_run
        elif isinstance(next_run, str):
            self.next_run = datetime.fromisoformat(next_run)
        else:
            raise TypeError(f'next_run must be datetime or str, not {type(next_run)}')
        # limit_count
        if isinstance(limit_count, int):
            self.limit_count = limit_count
        elif isinstance(limit_count, str):
            self.limit_count = int(limit_count)
        else:
            raise TypeError(f'limit_count must be int or str, not {type(limit_count)}')
        # limit_time
        if isinstance(limit_time, time):
            self.limit_time = limit_time
        elif isinstance(limit_time, str):
            self.limit_time = time.fromisoformat(limit_time)
        else:
            raise TypeError(f'limit_time must be time or str, not {type(limit_time)}')
        # role
        if isinstance(role, str):
            self.role = role
        else:
            raise TypeError(f'role must be str, not {type(role)}')





