# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QObject, Slot, Signal

from module.logger import logger


class Utils(QObject):

    def __init__(self) -> None:
        super(Utils, self).__init__()

    @Slot(result="QString")
    def current_datetime(self) -> str:
        """
        获取当前的时间
        :return:
        """
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")





if __name__ == "__main__":
    u = Utils()
    print(u.current_datetime())
