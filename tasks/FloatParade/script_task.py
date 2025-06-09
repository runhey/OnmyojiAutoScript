# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from tasks.TalismanPass.assets import TalismanPassAssets
from tasks.FloatParade.assets import FloatParadeAssets
from tasks.FloatParade.config import FloatParadeConfig, LevelReward

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer

class ScriptTask(GameUi, FloatParadeAssets, TalismanPassAssets):

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_main)
        con: FloatParadeConfig = self.config.float_parade.float_parade

        # 收取全部奖励
        self.get_all()
        # 回退
        while 1:
            self.screenshot()
            if self.appear(self.I_FP_TASKS):
                break
            if self.appear_then_click(self.I_BACK_Y, interval=3):
                continue
        logger.info('Goback to float parade main page')
        # 收取花车等级奖励
        self.get_flower(con.level_reward)
        # main page
        self.ui_get_current_page()
        self.ui_goto(page_main)

        self.set_next_run(task='FloatParade', success=True, finish=True)
        raise TaskEnd('FloatParade')


    def get_all(self):
        """
        一键收取所有的, 从庭院进入
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear(self.I_FP_UPGRADE):
                break
            if self.appear_then_click(self.I_FP_ACCESS, interval=0.8):
                continue
            if self.appear_then_click(self.I_FP_RED_CLOSE, interval=1.5):
                continue
            if self.appear_then_click(self.I_FP_TASKS, interval=1.8):
                continue
            if self.appear_then_click(self.I_TOGGLE_BUTTON, interval=3):
                continue
        logger.info('Enter float parade')
        logger.info('Click get all reward')
        if not self.appear(self.I_FP_GETALL1):
            logger.info('No appear get all button')
            return
        self.ui_get_reward(self.I_FP_GETALL1)
        logger.info('Got all reward')

    def get_flower(self, level: LevelReward = LevelReward.TWO):
        """
        收取花合战等级奖励
        :return:
        """
        match_level = {
            LevelReward.ONE: self.I_TP_LEVEL_1,
            LevelReward.TWO: self.I_TP_LEVEL_2,
            LevelReward.THREE: self.I_TP_LEVEL_3,
        }
        self.screenshot()
        if not self.appear(self.I_FP_GETALL0):
            logger.info('No any level reward')
            return
        logger.info('Appear level reward')
        # self.ui_click(self.I_FP_GETALL0, self.I_TP_GET_ALL)
        logger.info('Click level reward')
        check_timer = Timer(2)
        check_timer.start()
        while 1:
            self.screenshot()
            # 批量选择
            if self.appear_then_click(self.I_BATCH_SELECTION, interval=1.5):
                continue
            if self.appear_then_click(self.I_BATCH_SELECTION_CONFIRM, interval=0.8):
                continue

            if self.appear_then_click(match_level[level], interval=0.8):
                logger.info(f'Select {level} reward')
                if self.appear_then_click(self.I_OVERFLOW_CONFIRME, interval=0.8):
                    pass
                check_timer.reset()
                continue

            if self.ui_reward_appear_click(False):
                logger.info('Get reward')
                check_timer.reset()
                continue
            if check_timer.reached():
                logger.warning('No reward and break')
                break
            if self.appear_then_click(self.I_FP_GETALL0, interval=2.1):
                logger.info('Get all reward')
                check_timer.reset()
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
