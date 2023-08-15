# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from cached_property import cached_property

from tasks.GlobalGame.config import TeamFlow, Transport

from module.team_flow.mqtt import Mqtt
from module.config.config import Config
from module.team_flow.player import Player
from module.team_flow.task import Task

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
            if key == 'orochi':
                continue
            elif key == 'fallen_sun':
                continue
            elif key == 'eternity_sea':
                continue
            elif key == 'evo_zone':
                continue
            elif key == 'soul':
                continue
            else:
                continue




if __name__ == '__main__':
    host = Host(Config('oas1'))
