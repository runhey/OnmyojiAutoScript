# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from module.logger import logger
from module.exception import TaskEnd

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_delegation


class ScriptTask(GameUi):

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_delegation)

        self.set_next_run(task='Delegation', success=True, finish=True)
        raise TaskEnd



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from memory_profiler import profile
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()



