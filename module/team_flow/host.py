# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import json
from time import sleep
from datetime import datetime, time
from cached_property import cached_property

from tasks.GlobalGame.config import TeamFlow, Transport

from module.team_flow.mqtt import Mqtt
from module.config.config import Config
from module.team_flow.player import Player
from module.team_flow.task import Task
from module.logger import logger

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload)
    except json.JSONDecodeError:
        logger.error(f'Get [{msg.topic}]: {msg.payload}')
        return
    logger.info(f'Get {msg.topic}: {data}')
    for username, data in data.items():
        # 反正只有一项
        if username == userdata.username:
            continue
        userdata.match_topic[msg.topic](username, data)

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

    def on_first_notice(self, player: str, data: dict):
        # 其他人上线，就广播自己的策略出去
        if 'type' in data:
            logger.info(f'Player {player} is online')
            self.q_publish.put(['Strategy', self.publish_data()])
        else:
            # 如果是其他人像
            pass

    def on_last_will(self, player: str, data: dict):
        if player not in self.players:
            logger.warning(f'Player {player} is not in players')
            return
        self.players.remove(player)
        logger.info(f'Player {player} is offline')
        self._config_to_player()
        self._update_strategy()
        self._player_to_config()
        self.q_publish.put(['Strategy', self.publish_data()])

    def on_task_start(self, player: str, data: dict):
        pass

    def on_strategy(self, player: str, data: dict):
        pass

    def _config_to_player(self):
        """
        作为主角， 更新自身的多人任务的缓存
        也就是从  config -> multi_tasks
        :return:
        """
        tasks = {'orochi': self.config.model.orochi,
                 'fallen_sun': self.config.model.fallen_sun,
                 'eternity_sea': self.config.model.eternity_sea,
                 'evo_zone': self.config.model.evo_zone,
                 'exploration': self.config.model.exploration
                 }
        for key, value in tasks.items():
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
                role = 'leader'
                continue
            else:
                continue
            if not value.scheduler.enable:
                continue
            if task_name not in self.multi_tasks:
                # 第一次
                logger.info(f'First time to add [{task_name}] to multi_tasks')
                self.multi_tasks[task_name] = Task(
                    next_run=value.scheduler.next_run,
                    target_run=value.scheduler.next_run,
                    limit_time=limit_time,
                    team_task=True,
                    role=role,
                    limit_count=limit_count,
                )
            else:
                # 更新
                logger.info(f'Update {task_name} to multi_tasks')
                self.multi_tasks[task_name].update_info(next_run=value.scheduler.next_run,
                                                        limit_time=limit_time,
                                                        role=role,
                                                        limit_count=limit_count)

    def _player_to_config(self):
        for key, value in self.multi_tasks.items():
            if key == 'orochi':
                self.config.task_delay(task='Orochi', target=value.next_run)
            elif key == 'fallen_sun':
                self.config.task_delay(task='FallenSun', target=value.next_run)
            elif key == 'eternity_sea':
                self.config.task_delay(task='EternitySea', target=value.next_run)
            elif key == 'evo_zone':
                self.config.task_delay(task='EvoZone', target=value.next_run)
            elif key == 'exploration':
                # TODO 等待探索完成
                pass
            else:
                continue

    def _update_strategy(self):
        """
        更新策略:
        :return:
        """
        pass




if __name__ == '__main__':
    host = Host(Config('oas1'))
    sleep(20)
    # 更新config -> multi_tasks -> publish_data
    host._config_to_player()
    host.q_publish.put(['Strategy' ,host.publish_data()])
    host.q_publish.put(['Strategy' ,host.publish_data()])
    host.q_publish.put(['Strategy' ,host.publish_data()])
    sleep(46)

