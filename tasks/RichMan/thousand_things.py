# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from module.logger import logger

from tasks.GameUi.page import page_main, page_travel
from tasks.GameUi.game_ui import GameUi
from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import ThousandThings as ConfigThousandThings

class ThousandThings(GameUi, RichManAssets):

    def execute_tt(self, con: ConfigThousandThings) -> None:
        """

        :param con:
        :return:
        """
        logger.hr('Start Thousand Things')
        if not con.enable:
            logger.info('Thousand Things is disabled')
            return
        self.ui_get_current_page()
        self.ui_goto(page_travel)

        while 1:
            self.screenshot()
            if self.appear(self.I_TT_CHECK):
                break
            if self.appear_then_click(self.I_TT_ENTER, interval=1):
                continue
        logger.info('Enter Thousand Things')
        self.screenshot()
        if not self.appear(self.I_TT_TICKET_BULE) and not self.appear(self.I_TT_BLACK) and not self.appear(self.I_TT_AP):
            time.sleep(1)
        if con.mystery_amulet:
            self.tt_buy_mystery_amulet()
        if con.black_daruma_fragment:
            self.tt_buy_black_daruma_scrap()
        if con.ap:
            self.tt_buy_ap()
        while 1:
            self.screenshot()
            if self.appear(self.I_TT_ENTER):
                break
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1):
                continue
        logger.info('Exit Thousand Things')


    def tt_buy_mystery_amulet(self) -> bool:
        """

        :return: 成功购买返回True，找不到或者是钱不够返回False
        """
        self.screenshot()
        if not self.appear(self.I_TT_TICKET_BULE):
            logger.info('No mystery amulet')
            return False
        if not self.tt_check_memory(2000):
            return False
        while 1:
            self.screenshot()
            if self.appear(self.I_TT_BUY_UP):
                break
            if self.ocr_appear_click(self.O_TT_BLUE_TICKET, interval=1):
                continue
        logger.info('Buy mystery amulet')
        self.ui_get_reward(self.I_TT_BUY_CONFIRM)
        logger.info('Buy mystery amulet success')
        time.sleep(0.5)
        return True


    def tt_buy_black_daruma_scrap(self):
        self.screenshot()
        if not self.appear(self.I_TT_BLACK):
            logger.info('No black daruma scrap')
            return False
        if not self.tt_check_memory(350):
            return False
        while 1:
            self.screenshot()
            if self.appear(self.I_TT_BUY_UP):
                break
            if self.ocr_appear_click(self.O_TT_BLACK, interval=1):
                continue
        logger.info('Buy black daruma scrap')
        self.ui_get_reward(self.I_TT_BUY_CONFIRM)
        logger.info('Buy black daruma scrap success')
        time.sleep(0.5)
        return True

    def tt_buy_ap(self):
        self.screenshot()
        if not self.appear(self.I_TT_AP):
            logger.info('No ap')
            return False
        if not self.tt_check_memory(600):
            return False
        self.O_TT_NUMBER.keyword = '2'
        while 1:
            self.screenshot()
            if self.ocr_appear(self.O_TT_NUMBER):
                break
            if self.appear_then_click(self.I_TT_BUY_UP, interval=0.5):
                continue
            if self.ocr_appear_click(self.O_TT_AP, interval=1):
                continue
        logger.info('Buy ap')
        self.ui_get_reward(self.I_TT_BUY_CONFIRM)
        logger.info('Buy ap success')
        time.sleep(0.5)
        return True

    def tt_check_memory(self, mix: int) -> bool:
        self.screenshot()
        current = self.O_TT_TOTOL.ocr(self.device.image)
        if not isinstance(current, int):
            logger.warning('OCR current memory failed')
            return False
        if current >= mix:
            logger.info('Memory is enough')
            return True
        logger.info('Memory is not enough')
        return False


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from memory_profiler import profile
    c = Config('oas1')
    d = Device(c)
    t = ThousandThings(c, d)

    t.execute_tt(t.config.rich_man.thousand_things)




