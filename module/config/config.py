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
from module.config.config_menu import ConfigMenu
from module.config.config_model import ConfigModel
from module.config.config_state import ConfigState
from module.config.utils import *

from module.logger import logger

class Config(ConfigState, ConfigManual, ConfigWatcher, ConfigMenu):

    def __init__(self, config_name: str, task=None) -> None:
        """

        :param config_name:
        :param task:
        """
        super().__init__(config_name)  # 调用 ConfigState 的初始化方法
        super(ConfigManual, self).__init__()
        super(ConfigWatcher, self).__init__()
        super(ConfigMenu, self).__init__()
        self.model = ConfigModel(config_name=config_name)

    def __getattr__(self, name):
        """
        一开始是打算直接继承ConfigModel的，但是pydantic会接管所有的变量
        故而选择持有ConfigModel
        :param name:
        :return:
        """
        try:
            return getattr(self.model, name)
        except AttributeError:
            logger.error(f'can not ask this variable {name}')
            return None  # 或者抛出异常，或者返回其他默认值

    def gui_args(self, task: str) -> str:
        """
        获取给gui显示的参数
        :return:
        """
        return self.model.gui_args(task=task)

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
    config = Config(config_name='pydantic')
    print(config.menu)
    print(config.config_name)

    config.script.device.serial = 123
    print(config.script.device.serial)

