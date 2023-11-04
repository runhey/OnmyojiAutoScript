# This Python file uses the following encoding: utf-8
# @author runhey
# 主进程的管理
# github https://github.com/runhey
from multiprocessing.managers import SyncManager

from module.logger import logger
from module.config.config import Config
from module.server.script_process import ScriptProcess
from module.server.config_manager import ConfigManager

class MainManager(ConfigManager):
    config_cache :Config = None  # 缓存当前切换的配置
    script_process :dict[str: ScriptProcess] = None  # 脚本进程

    def __init__(self) -> None:
        super().__init__()



    def ensure_config_cache(self, config_name):
        if self.config_cache is None:
            if config_name not in self.all_script_files():
                logger.warning(f'[{config_name}] script file does not exist')
                return None
            self.config_cache = Config(config_name)
        elif self.config_cache.config_name != config_name:
            self.config_cache = Config(config_name)
        return self.config_cache





