# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import zerorpc
import zmq
import random
from cached_property import cached_property

from module.logger import logger
from module.exception import *

class Script:
    def __init__(self, config_name: str ='oas') -> None:
        self.server = None
        self.config_name = config_name

    @cached_property
    def config(self) -> "Config":
        try:
            from module.config.config import Config
            config = Config(config_name=self.config_name)
            return config
        except RequestHumanTakeover:
            logger.critical('Request human takeover')
            exit(1)
        except Exception as e:
            logger.exception(e)
            exit(1)

    # @cached_property
    # def device(self) -> "Device":
    #     try:
    #         from module.device.device import Device
    #         device = Device(config=self.config)
    #         return device
    #     except RequestHumanTakeover:
    #         logger.critical('Request human takeover')
    #         exit(1)
    #     except Exception as e:
    #         logger.exception(e)
    #         exit(1)

    def init_server(self, port: int) -> int:
        """
        初始化zerorpc服务，返回端口号
        :return:
        """
        self.server = zerorpc.Server(self)
        try:
            self.server.bind(f'tcp://127.0.0.1:{port}')
            return port
        except zmq.error.ZMQError:
            logger.error(f"Ocr server cannot bind on port {port}")
            return None


    def run_server(self) -> None:
        """
        启动zerorpc服务
        :return:
        """
        self.server.run()

    def gui_args(self, task: str) -> str:
        """
        获取给gui显示的参数
        :return:
        """
        return self.config.gui_args(task=task)

    def gui_menu(self) -> str:
        """
        获取给gui显示的菜单
        :return:
        """
        return self.config.gui_menu


