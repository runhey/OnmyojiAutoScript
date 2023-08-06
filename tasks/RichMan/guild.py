# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from module.logger import logger

from tasks.GameUi.page import page_main, page_guild
from tasks.GameUi.game_ui import GameUi
from tasks.Component.Buy.buy import Buy
from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import GuildStore

class Guild(Buy, GameUi, RichManAssets):

    def execute_guild(self, con: GuildStore=None):
        logger.hr('Start guild', 1)
        self.ui_get_current_page()
        self.ui_goto(page_guild)
        while 1:
            self.screenshot()
            if self.appear(self.I_GUILD_CLOSE_RED):
                break
            if self.appear_then_click(self.I_GUILD_SHRINE, interval=0.8):
                continue
            if self.appear_then_click(self.I_GUILD_STORE, interval=1.1):
                continue
        logger.info('Enter guild store success')
        time.sleep(0.5)
        while 1:
            self.screenshot()
            if self.appear(self.I_GUILD_SCRAP):
                break
            if self.swipe(self.S_GUILD_STORE, interval=1.5):
                time.sleep(2)
                continue

        # 开始购买
        if con.mystery_amulet:
            self._guild_mystery_amulet()
        if con.black_daruma_scrap:
            self._guild_black_daruma_scrap()
        if con.skin_ticket:
            self._guild_skin_ticket(con.skin_ticket)

        # 回去
        while 1:
            self.screenshot()
            if self.appear(self.I_GUILD_SHRINE):
                break
            if self.appear_then_click(self.I_GUILD_CLOSE_RED, interval=1):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1):
                continue

    def _guild_mystery_amulet(self):
        logger.hr('Guild mystery amulet', 2)
        self.screenshot()
        if not self.buy_check_money(self.O_GUILD_TOTAL, 240):
            return False
        number = self.O_GUILD_NUMBER_BLUE.ocr(self.device.image)
        if not isinstance(number, int):
            logger.warning('OCR number failed')
            return False
        if number == 0:
            logger.warning('No mystery amulet can buy')
            return False
        self.buy_more(self.I_GUILD_BLUE, number)
        time.sleep(0.5)
        return True

    def _guild_black_daruma_scrap(self):
        logger.hr('Guild black daruma scrap', 2)
        self.screenshot()
        if not self.buy_check_money(self.O_GUILD_TOTAL, 200):
            return False
        number = self.O_GUILD_NUMBER_BLACK.ocr(self.device.image)
        if not isinstance(number, int):
            logger.warning('OCR number failed')
            return False
        if number == 0:
            logger.warning('No black daruma can buy')
            return False
        self.buy_one(self.I_GUILD_SCRAP, self.I_GUILD_CHECK_SCRAP)
        time.sleep(0.5)
        return True

    def _guild_skin_ticket(self, num: int=0):
        logger.hr('Guild skin ticket', 2)
        if num == 0:
            logger.warning('No buy skin ticket')
            return False
        self.screenshot()
        if not self.buy_check_money(self.O_GUILD_TOTAL, 50):
            return False
        number = self.O_GUILD_NUMBER_SKIN.ocr(self.device.image)
        if not isinstance(number, int):
            logger.warning('OCR number failed')
            return False
        if number == 0:
            logger.warning('No skin ticket can buy')
            return False
        self.buy_more(self.I_GUILD_SKIN, number)
        time.sleep(0.5)
        return True



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = Guild(c, d)

    t._guild_skin_ticket(5)



