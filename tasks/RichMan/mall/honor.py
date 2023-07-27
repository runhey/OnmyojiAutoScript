# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from module.logger import logger

from tasks.GameUi.page import page_main, page_guild
from tasks.GameUi.game_ui import GameUi
from tasks.Component.Buy.buy import Buy
from tasks.RichMan.mall.navbar import MallNavbar
from tasks.RichMan.mall.special import Special
from tasks.RichMan.config import HonorRoom


class Honor(Special):

    def execute_honor(self, con: HonorRoom = None):
        if not con:
            con = self.config.rich_man.honor_room
        if not con.enable:
            logger.info('Honor is not enable')
            return
        self._enter_honor()
        self._honor_mystery_amulet(con.mystery_amulet)
        self._honor_black_daruma_scrap(con.black_daruma_scrap)


    def _honor_mystery_amulet(self, enable: bool=False):
        logger.hr('Buy mystery amulet', 3)
        if not enable:
            logger.info('Buy mystery amulet is disabled')
            return

        self.screenshot()
        if not self.appear(self.I_HONOR_BLUE):
            logger.warning('No appear mystery amulet')
            return
        # 检查剩余数量
        # remain_number = self.O_HONOR_BLUE.ocr(self.device.image)
        remain_number = self._special_check_remain(self.I_HONOR_BLUE)
        if not isinstance(remain_number, int):
            logger.warning('Can not get remain number')
            return
        if remain_number == 0:
            logger.warning(f'No blue honor {remain_number}')
            return
        if not self.mall_check_money(4, 1500):
            logger.warning('No enough money')
            return
        # 点击购买
        self.buy_more(self.I_HONOR_BLUE)
        time.sleep(1)

    def _honor_black_daruma_scrap(self, enable: bool=False):
        logger.hr('Buy black daruma scrap', 3)
        if not enable:
            logger.info('Buy black daruma scrap is disabled')
            return

        self.screenshot()
        if not self.appear(self.I_HONOR_BLACK):
            logger.warning('No appear black daruma scrap')
            return
        # 检查剩余数量
        # remain_number = self.O_HONOR_BLACK.ocr(self.device.image)
        remain_number = self._special_check_remain(self.I_HONOR_BLACK)
        if not isinstance(remain_number, int):
            logger.warning('Can not get remain number')
            return
        if remain_number == 0:
            logger.warning(f'No black daruma scrap {remain_number}')
            return
        if not self.mall_check_money(4, 540):
            logger.warning('No enough money')
            return
        # 点击购买
        self.buy_more(self.I_HONOR_BLACK)
        time.sleep(0.5)





if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = Honor(c, d)

    t.execute_honor()




