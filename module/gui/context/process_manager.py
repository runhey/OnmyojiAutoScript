# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import socket
import random
import zerorpc

from PySide6.QtCore import QObject, Slot, Signal

from module.gui.process.script_process import ScriptProcess
from module.gui.context.add import Add
from module.logger import logger


def is_port_in_use(ip, port) -> bool:
    """
    检查端口是否被占用
    :param ip:
    :param port:
    :return:
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, port))
        s.shutdown(2)
        logger.info(f'port {port} is in use')
        return True
    except:
        logger.info(f'port {port} is not in use')
        return False




class ProcessManager(QObject):
    """
    进程管理
    """

    def __init__(self) -> None:
        """
        init
        """
        super().__init__()
        self.processes = {}  # 持有所有的进程
        self.ports = {}  # 持有所有的端口
        self.clients = {}  # zerorpc连接的客户端

    @Slot()
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
            port = 40000 + random.randint(0, 200)
            while is_port_in_use('127.0.0.1', port):
                port = 40000 + random.randint(0, 200)
            self.ports[config] = port
            self.processes[config] = ScriptProcess(config, port)
            logger.info(f'create script {config} on port {port}')
            try:
                self.clients[config] = zerorpc.Client()
                self.clients[config].connect(f'tcp://127.0.0.1:{self.ports[config]}')
            except:
                logger.exception(f'connect to script {config} error')
                raise
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
            del self.ports[config]
            del self.clients[config]
            logger.info(f'remove script {config}')
            logger.info(f'port {config} is released')
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