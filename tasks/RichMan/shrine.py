# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from module.logger import logger

from tasks.GameUi.page import page_main, page_summon
from tasks.GameUi.game_ui import GameUi
from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import Shrine as ConfigShrine


class Shrine(GameUi, RichManAssets):

    def execute_shrine(self, con: ConfigShrine):
        logger.hr('Start Shrine')
        if not con.enable:
            logger.info('Shrine is disabled')
            return
        self.ui_get_current_page()
        self.ui_goto(page_summon)

        while 1:
            self.screenshot()
            if self.appear(self.I_S_NEXT_PERIOD):
                break
            # if self.click(self.C_C_SHRINE, interval=1):
            #     continue
            if self.appear_then_click(self.I_CENTER1, interval=1):
                continue
            if self.appear_then_click(self.I_CENTER2, interval=1):
                continue
        logger.info('Enter Shrine')
        time.sleep(0.5)
        if con.black_daruma:
            self.shrine_black_daruma()
        if con.white_daruma_five:
            self.shrine_white_five()
        if con.white_daruma_four:
            self.shrine_white_four()

    def shrine_check_money(self, mix: int) -> bool:
        self.screenshot()
        current = self.O_TT_TOTOL.ocr(self.device.image)
        if not isinstance(current, int):
            logger.warning('OCR current money failed')
            return False
        if current >= mix:
            logger.info('Money is enough')
            return True
        logger.info('Money is not enough')
        return False

    def _check_bought(self, target) -> bool:
        """
        检查是否已经购买, 弃用，无法识别任何文字
        :return: True 已经购买
        """
        self.screenshot()
        result = target.ocr(self.device.image)
        if '已' in result or '兑' in result or '换' in result:
            logger.info('Already bought')
            return True
        logger.info('Not bought')
        return False

    def shrine_black_daruma(self):
        logger.hr('Shrine black daruma', 2)
        self.screenshot()
        if not self.shrine_check_money(1500):
            return
        if not self.appear(self.I_S_BLACK):
            logger.info('Already bought black daruma')
            return
        self.ui_click(self.I_S_BLACK, self.I_S_CHECK_BLACK)
        self.screenshot()
        if not self.appear(self.I_S_BUY_BLACK, threshold=0.6):
            logger.info('Already bought black daruma')
            self.ui_click_until_disappear(self.I_UI_BACK_RED)
            time.sleep(0.5)
            return
        self.ui_click(self.I_S_BUY_BLACK, self.I_S_CONFIRM_BLACK)
        self.ui_get_reward(self.I_S_CONFIRM_BLACK)
        self.ui_click_until_disappear(self.I_UI_BACK_RED)
        time.sleep(1)

    def shrine_white_five(self):
        logger.hr('Shrine white five', 2)
        self.screenshot()
        if not self.appear(self.I_S_WHITE_FIVE):
            logger.info('White five is not available')
            return
        if not self.shrine_check_money(1200):
            return
        self.ui_click(self.I_S_WHITE_FIVE, self.I_S_CHECK_WHITE_FIVE)
        self.screenshot()
        if not self.appear(self.I_S_BUY_WHITE_FIVE, threshold=0.9):
            logger.info('Already bought white five')
            self.ui_click_until_disappear(self.I_UI_BACK_RED)
            time.sleep(1)
            return
        self.ui_click(self.I_S_BUY_WHITE_FIVE, self.I_S_CONFIRM_WHITE_FIVE)
        self.ui_get_reward(self.I_S_CONFIRM_WHITE_FIVE)
        self.ui_click_until_disappear(self.I_UI_BACK_RED)
        time.sleep(1)

    def shrine_white_four(self):
        logger.hr('Shrine white four', 2)
        self.screenshot()
        if not self.appear(self.I_S_WHITE_FOUR):
            logger.info('White four is not available')
            return
        if not self.shrine_check_money(400):
            return
        self.ui_click(self.I_S_WHITE_FOUR, self.I_S_CHECK_WHITE_FOUR)
        self.screenshot()
        if not self.appear(self.I_S_BUY_WHITE_FOUR, threshold=0.9):
            logger.info('Already bought white four')
            self.ui_click_until_disappear(self.I_UI_BACK_RED)
            time.sleep(1)
            return
        self.ui_click(self.I_S_BUY_WHITE_FOUR, self.I_S_CONFIRM_WHITE_FOUR)
        self.ui_get_reward(self.I_S_CONFIRM_WHITE_FOUR)
        self.ui_click_until_disappear(self.I_UI_BACK_RED)
        time.sleep(1)



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = Shrine(c, d)

    # t.shrine_white_four()
    t.execute_shrine(t.config.model.rich_man.shrine)
    # t.screenshot()
    # print(t.appear(t.I_S_BUY_WHITE_FIVE, threshold=0.9))

