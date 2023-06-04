# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import socket
import random
import zerorpc
import cv2
import msgpack
import numpy as np
import io

from typing import Union, Any
from PySide6.QtCore import QObject, Slot, Signal, QByteArray, QBuffer
from PySide6.QtGui import QImage

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

    def get_client(self, config: str) -> zerorpc.Client:
        """
        get_client
        :param config:
        :return:
        """
        if config in self.clients:
            return self.clients[config]
        else:
            logger.info(f'script {config} is not running')
            return None

    @Slot(str, result="QString")
    def gui_menu(self, config: str) -> str:
        """
        get_gui_menu
        :param config:
        :return:
        """
        if config in self.clients:
            logger.info(f'gui get menu of {config}')
            return self.clients[config].gui_menu()
        else:
            logger.info(self.clients)
            logger.info(f'script {config} is not running')
            return None

    @Slot(str, str, result="QString")
    def gui_args(self, config: str, task: str) -> str:
        """
        获取显示task的gui参数
        :param config:
        :param task:
        :return:
        """
        if config in self.clients:
            logger.info(f'gui get args of {config} {task}')
            return self.clients[config].gui_args(task)
        else:
            logger.info(f'script {config} is not running')
            return None

    @Slot(str, str, result="QString")
    def gui_task(self, config: str, task: str) -> str:
        """
        获取显示task的gui
        :param config:
        :param task:
        :return:
        """
        if config in self.clients:
            logger.info(f'gui get value of {config} {task}')
            return self.clients[config].gui_task(task)
        else:
            logger.info(f'script {config} is not running')
            return None

    @Slot(str, str, str, str, str, result="bool")
    def gui_set_task(self, config: str, task: str, group: str, arg: str, value) -> bool:
        """
        设置task的gui   是string类型的
        :param config:
        :param task:
        :param group:
        :param arg:
        :param value:
        :return:
        """
        if config in self.clients:
            logger.info(f'gui set value of {config} {task}')
            if self.clients[config].gui_set_task(task, group, arg, value):
                return True
            else:
                return False
        else:
            logger.info(f'script {config} is not running')
            return False

    @Slot(str, str, str, str, bool, result="bool")
    def gui_set_task_bool(self, config: str, task: str, group: str, arg: str, value: bool) -> bool:
        """
        设置task的gui   是bool类型的
        :param config:
        :param task:
        :param group:
        :param arg:
        :param value:
        :return:
        """
        if config in self.clients:
            logger.info(f'gui set value of {config} {task}')
            if self.clients[config].gui_set_task(task, group, arg, value):
                return True
            else:
                return False
        else:
            logger.info(f'script {config} is not running')
            return False

    @Slot(str, str, str, str, float, result="bool")
    def gui_set_task_number(self, config: str, task: str, group: str, arg: str, value) -> bool:
        """
        设置task的gui   是float类型的或者是int
        :param config:
        :param task:
        :param group:
        :param arg:
        :param value:
        :return:
        """
        if config in self.clients:
            logger.info(f'gui set value of {config} {task}')
            if self.clients[config].gui_set_task(task, group, arg, value):
                return True
            else:
                return False
        else:
            logger.info(f'script {config} is not running')
            return False

    @Slot(str, result="QImage")
    def gui_mirror_image(self, config: str) -> QImage:
        """
        :param config:
        :return:
        """
        if config in self.clients:
            logger.info(f'gui get mirror image of {config}')
            # 接收流对象
            stream = self.clients[config].gui_mirror_image()
            # 创建 BytesIO 对象来存储图像数据
            buffer = io.BytesIO()
            for data in stream:
                buffer.write(data)
            # 将 BytesIO 对象的内容作为字节流解码为 cv2 图像
            buffer.seek(0)  # 将读取位置重置为起始位置
            image_data = np.frombuffer(buffer.getvalue(), dtype=np.uint8)
            image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)

            height, width, _ = image.shape
            image_qt = QImage(image.data, width, height, QImage.Format_RGB888).rgbSwapped()
            return image_qt



        else:
            logger.info(f'script {config} is not running')
            return None
