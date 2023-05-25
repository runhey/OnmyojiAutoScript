# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import copy
import datetime
import operator
import threading

from module.config.config_updater import ConfigUpdater
from module.config.config_manual import ConfigManual
from module.config.config_watcher import ConfigWatcher
from module.config.utils import *

from module.logger import logger

class Config(ConfigManual, ConfigWatcher, ConfigUpdater):
    """
    一个配置文件的集成类
    """
    def __init__(self, config_name: str, task=None) -> None:
        """

        :param config_name:
        :param task:
        """
        self.config_name = config_name
        self.data: dict = {}
        self.is_template_config = config_name.startswith("template")

        self.load()


    def load(self) -> None:
        self.data = self.read_file(self.config_name)


    def get_arg(self, task: str, group: str, argument: str):
        """

        :param task:
        :param group:
        :param argument:
        :return: str/int/float
        """
        try:
            return self.data[task][group][argument]
        except:
            logger.exception(f'have no arg {task}.{group}.{argument}')

    def set_arg(self, task: str, group: str, argument: str, value) -> None:
        """

        :param task:
        :param group:
        :param argument:
        :param value:
        :return:
        """
        try:
            self.data[task][group][argument] = value
        except:
            logger.exception(f'have no arg {task}.{group}.{argument}')

if __name__ == '__main__':
    config = Config(config_name='oas1')
    logger.info(config.data)
    logger.info(config.get_arg("Script", "Device", "Serial"))
