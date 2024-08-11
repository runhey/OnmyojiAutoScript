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

    @Slot(str, str, str, result="QString")
    def test_notify(self, _config: str, title: str, content: str) -> bool:
        from module.notify.notify import Notifier
        try:
            notifier = Notifier(_config, True)
            if notifier.push(title=title, content=content):
                return "true"
            else:
                return "false"
        except Exception as e:
            logger.exception(e)
            return "false"



if __name__ == "__main__":
    u = Utils()
    print(u.current_datetime())
