# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from pydantic.deprecated import config
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from tasks.TalismanPass.assets import TalismanPassAssets
from tasks.FloatParade.assets import FloatParadeAssets
from tasks.FloatParade.config import FloatParadeConfig, LevelReward
from tasks.Component.RightActivity.right_activity import RightActivity

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer

class ScriptTask(RightActivity, FloatParadeAssets, TalismanPassAssets):

    def run(self):
        con: FloatParadeConfig = self.config.float_parade.float_parade
        self.enter(self.I_FP_ACCESS)
        logger.info('Enter float parade')
        while 1:
            self.screenshot()
            if self.appear(self.I_FP_UPGRADE):
                break
            if self.appear_then_click(self.I_FP_ACCESS, interval=0.8):
                continue
            if self.appear_then_click(self.I_FP_RED_CLOSE, interval=1.5):
                continue
            if self.appear_then_click(self.I_FP_GIFT_CLOSE, interval=3):
                continue
            # if self.appear_then_click(self.I_TOGGLE_BUTTON, interval=3):
            #     continue

        # 收取 放置里程
        self.get_mileage()

        # 收取花车等级奖励
        self.get_flower(con.level_reward1, con.level_reward2) # 第一种

        # main page
        self.ui_get_current_page()
        self.ui_goto(page_main)

        self.set_next_run(task='FloatParade', success=True, finish=True)
        raise TaskEnd('FloatParade')

    def get_mileage(self):
        self.screenshot()
        if not self.appear(self.I_ENTRY_MILEAGE):
            return
        logger.hr("Get mileage reward")
        self.ui_click( click=self.I_ENTRY_MILEAGE, stop=self.I_CLAIM_MILEAGE, interval=1.9)
        self.ui_get_reward(self.I_CLAIM_MILEAGE)
        self.ui_click_until_disappear(self.I_UI_BACK_RED, interval=1.8)
        logger.info('Got mileage reward')

    def get_flower(self, level1: LevelReward = LevelReward.TWO, level2: LevelReward = LevelReward.TWO):
        """
        收取花合战等级奖励
        :return:
        """
        match_level = {
            LevelReward.ONE: self.I_FP_SELECT_1,
            LevelReward.TWO: self.I_FP_SELECT_2,
            LevelReward.THREE: self.I_FP_SELECT_3,
        }
        logger.info('Click level reward')
        check_timer = Timer(2)
        check_timer.start()
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_UI_BACK_RED, interval=0.8):
                continue
            # 批量选择
            if self.appear_then_click(self.I_BATCH_SELECTION, interval=1.5):
                continue
            if self.appear_then_click(self.I_BATCH_SELECTION_CONFIRM, interval=0.8):
                continue

            if self.appear(self.I_FP_GIFT_FLAG1) and self.appear_then_click(match_level[level1], interval=0.8):
                logger.info(f'Select {level1} reward')
                if self.appear_then_click(self.I_OVERFLOW_CONFIRME, interval=0.8):
                    pass
                check_timer.reset()
                continue
            if self.appear(self.I_FP_GIFT_FLAG2) and self.appear_then_click(match_level[level2], interval=0.8):
                logger.info(f'Select {level2} reward')
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

            apper_get_all_0 = self.appear(self.I_FP_GETALL0)  # 出现一键领取就不大会点”任务“
            if apper_get_all_0:
                self.click(self.I_FP_GETALL0, interval=2.1)
                check_timer.reset()
                continue
            elif self.appear_then_click(self.I_FP_TASKS, interval=2.5):
                check_timer.reset()
                continue

            if self.appear_then_click(self.I_RED_POINT_0, interval=1.5):
                continue



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
