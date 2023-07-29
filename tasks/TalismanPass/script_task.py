# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_daily
from tasks.TalismanPass.assets import TalismanPassAssets

from module.logger import logger
from module.exception import TaskEnd

class ScriptTask(GameUi, TalismanPassAssets):

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_main)
        self.main_goto_daily()

        # 收取全部奖励
        self.get_all()
        # 收取花合战等级奖励
        self.get_flower()

        self.set_next_run(task='TalismanPass', success=True, finish=True)
        raise TaskEnd('TalismanPass')


    def get_all(self):
        """
        一键收取所有的
        :return:
        """
        self.screenshot()
        if not self.appear(self.I_TP_GET_ALL):
            logger.info('No appear get all button')
        self.ui_get_reward(self.I_TP_GET_ALL)
        logger.info('Get all reward')

    def get_flower(self):
        """
        收取花合战等级奖励
        :return:
        """
        pass

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()

