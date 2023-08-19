# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import datetime, time
from random import randint


from module.config.config import Config
from module.team_flow.task import Task

class Player:
    def __init__(self, username: str):
        self.username = username
        self.multi_tasks: dict[str: Task] = {}  # 缓存多人任务的列表


    def publish_data(self) -> dict:
        """
        提取要 发布的数据
        :return:
        """
        result = {}
        for name, task in self.multi_tasks.items():
            item = {}
            if not task.team_task:
                continue
            item['next_run'] = str(task.next_run)
            item['role'] = str(task.role)
            item['limit_time'] = str(task.limit_time)
            item['limit_count'] = int(task.limit_count)
            result[name] = item
        return result
