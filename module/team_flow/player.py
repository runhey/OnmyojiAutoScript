# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import datetime, time
from random import randint


from module.config.config import Config

class Player:
    def __init__(self, username: str):
        self.username = username
        self.multi_tasks: list = []  # 缓存多人任务的列表


    def publish_data(self) -> list:
        """
        提取要 发布的数据
        :return:
        """
        result = []
        for task in self.multi_tasks:
            item = {}
            if not task.team_task:
                continue
            item['task_name'] = task.task_name
            item['next_run'] = task.next_run
            item['role'] = task.role
            item['limit_time'] = task.limit_time
            item['limit_count'] = task.limit_count
            result.append(item)
        return result
