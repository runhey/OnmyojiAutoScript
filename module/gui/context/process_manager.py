# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.gui.process.script_process import ScriptProcess
from module.gui.context.add import Add
from module.logger import logger


class ProcessManager:
    """
    进程管理
    """

    def __init__(self) -> None:
        """
        init
        """
        super().__init__()
        self.processes = {}

    def create_all(self) -> None:
        """
        创建所有的配置实例
        :return:
        """
        configs = Add().all_script_files()
        for config in configs:
            self.add(config)

    def add(self, config: str) -> None:
        """
        add
        :param config:
        :return:
        """
        if config not in self.processes:
            self.processes[config] = ScriptProcess(config)
            self.processes[config].start()
            logger.info(f'add script {config}')
        else:
            logger.info(f'script {config} is already running')

    def remove(self, config: str) -> None:
        """
        remove
        :param config:
        :return:
        """
        if config in self.processes:
            self.processes[config].stop()
            del self.processes[config]
            logger.info(f'remove script {config}')
        else:
            logger.info(f'script {config} is not running')

    def restart(self, config: str) -> None:
        """
        restart
        :param config:
        :return:
        """
        if config in self.processes:
            self.processes[config].restart()
            logger.info(f'restart script {config}')
        else:
            logger.info(f'script {config} is not running')

    def stop_all(self) -> None:
        """
        stop_all
        :return:
        """
        for config in self.processes:
            self.processes[config].stop()
        logger.info(f'stop all script')

    def restart_all(self) -> None:
        """
        restart_all
        :return:
        """
        for config in self.processes:
            self.processes[config].restart()
        logger.info(f'restart all script')