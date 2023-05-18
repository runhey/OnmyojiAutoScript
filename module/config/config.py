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
    pass
