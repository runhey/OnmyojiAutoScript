# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import os
import json

from filelock import FileLock
from PySide6.QtCore import QObject, Slot

from module.logger import logger
from module.config.atomicwrites import atomic_write



class RuleFile(QObject):

    def __init__(self):
        super().__init__()

    @Slot(str, result="QString")
    def read_file(self, file: str) -> str:
        """
        读取json文件，如果不存在则创建
        :param file: 包含路径
        :return:
        """
        folder = os.path.dirname(file)
        if not os.path.exists(folder):
            os.mkdir(folder)

        if not os.path.exists(file):
            return ""

        _, ext = os.path.splitext(file)
        lock = FileLock(f"{file}.lock")
        with lock:
            logger.info(f'read: {file}')
            if ext == '.json':
                with open(file, mode='r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.error(f"not support {ext} file")
                return ""

    @Slot(str, str)
    def write_file(self, file: str, data: str) -> None:
        """
        写入json文件，如果不存在则创建
        :param file: 包含路径
        :param data: 写入的数据
        :return:
        """
        folder = os.path.dirname(file)
        if not os.path.exists(folder):
            os.mkdir(folder)

        _, ext = os.path.splitext(file)
        lock = FileLock(f"{file}.lock")
        with lock:
            logger.info(f'write: {file}')
            if ext == '.json':
                with atomic_write(file, overwrite=True, encoding='utf-8') as f:
                    f.write(data)
            else:
                logger.error(f"not support {ext} file")
