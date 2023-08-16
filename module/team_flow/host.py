# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, time
from cached_property import cached_property

from tasks.GlobalGame.config import TeamFlow, Transport

from module.team_flow.mqtt import Mqtt
from module.config.config import Config
from module.team_flow.player import Player
from module.team_flow.task import Task
from module.logger import logger

def on_message(client, userdata, msg):
    userdata.match_topic[msg.topic](msg.payload)

class Host(Mqtt, Player):

    def __init__(self, config: Config):
        Player.__init__(self, config.global_game.team_flow.username)
        Mqtt.__init__(self, config.global_game.team_flow)
        self.config = config
        self.players: list[Player] = []
        self.set_on_message(on_message)

    @cached_property
    def match_topic(self):
        return {
            'FirstNotice': self.on_first_notice,
            'LastWill': self.on_last_will,
            'TaskStart': self.on_task_start,
            'Strategy': self.on_strategy
        }

    def on_first_notice(self, payload):
        pass

    def on_last_will(self, payload):
        pass

    def on_task_start(self, payload):
        pass

    def on_strategy(self, payload):
        pass

    def update_multi_tasks(self):
        """
        作为主角， 更新自身的多人任务的缓存
        也就是从  config -> multi_tasks
        :return:
        """
        for key, value in self.config.model.items():
            task_name: str = key
            limit_time: time = None
            limit_count: int = None
            role: str = None
            if key == 'orochi':
                limit_time = value.orochi_config.limit_time
                limit_count = value.orochi_config.limit_count
                role = str(value.orochi_config.user_status)
            elif key == 'fallen_sun':
                limit_time = value.fallen_sun_config.limit_time
                limit_count = value.fallen_sun_config.limit_count
                role = str(value.fallen_sun_config.user_status)
            elif key == 'eternity_sea':
                limit_time = value.eternity_sea_config.limit_time
                limit_count = value.eternity_sea_config.limit_count
                role = str(value.eternity_sea_config.user_status)
            elif key == 'evo_zone':
                limit_time = value.evo_zone_config.limit_time
                limit_count = value.evo_zone_config.limit_count
                role = str(value.evo_zone_config.user_status)
            elif key == 'exploration':
                # TODO 等待探索完成
                limit_time = time(minute=30)
                limit_count = 50
                role = str(value.evo_zone_config.user_status)
                continue
            else:
                continue
            if not value.scheduler.enable:
                continue
            if task_name not in self.multi_tasks:
                # 第一次
                logger.info(f'First time to add {task_name} to multi_tasks')
                self.multi_tasks[task_name] = Task(
                    next_run=value.scheduler.next_run,
                    target_run=value.scheduler.target_run,
                    limit_time=limit_time,
                    team_task=True,
                    role=role,
                    limit_count=limit_count,
                )
            else:
                # 更新
                logger.info(f'Update {task_name} to multi_tasks')
                self.multi_tasks[task_name].next_run = value.scheduler.next_run
                self.multi_tasks[task_name].limit_time = limit_time
                self.multi_tasks[task_name].role = role
                self.multi_tasks[task_name].limit_count = limit_count





if __name__ == '__main__':
    host = Host(Config('oas1'))
