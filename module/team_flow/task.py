# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import datetime, time, timedelta
from random import randint

from module.config.config import Config

from tasks.Component.config_base import TimeDelta


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

    # ----------------------------------------------------------------------------------------------------------------------
    # 对于host来进行操作的函数
    def u(self) -> float:
        """
        效用函数
        :return:
        """
        if self.role == 'leader':
            return self.r_leader() - self.r_leader()
        elif self.role == 'member':
            return self.r_member() - self.c_member()

    def r_leader(self, tasks: list['Task']) -> float:
        """
        收益函数
        :param tasks: 在小组内的启用的同一任务列表
        :return:
        """
        result = 0
        for task in tasks:
            if task.role == 'leader':
                pass

        return result

    def c_leader(self) -> float:
        """
        成本函数
        :return:
        """

    def r_member(self) -> float:
        """
        收益函数
        :return:
        """

    def c_member(self) -> float:
        """
        成本函数
        :return:
        """


def t_diff(before: Task, after: Task) -> timedelta:
    """
    计算两个任务之间的时间差
    :param before:
    :param after:
    :return: 单位是秒
    """
    return (after.next_run - before.next_run).total_seconds()


if __name__ == '__main__':
    host = Task(next_run=datetime.fromisoformat('2023-09-13 18:46:23'),
                limit_time=time.fromisoformat('00:30:00'),
                target_run=datetime.fromisoformat('2023-09-13 18:46:23'),
                team_task=True, role='leader', limit_count=0)

    test1 = Task(next_run=datetime.fromisoformat('2023-09-13 18:44:23'),
                 limit_time=time.fromisoformat('00:30:00'),
                 target_run=datetime.fromisoformat('2023-09-13 18:46:23'),
                 team_task=True, role='leader', limit_count=0)

    print(t_diff(host, test1))
