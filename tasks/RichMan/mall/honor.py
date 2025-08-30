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
        
        # 向下滑找到购买的物品
        mystery_bought, black_bought = False, False
        max_swipes = 3
        swipe_count = 0
        
        while 1:
            self.screenshot()
            if not mystery_bought and con.mystery_amulet and self.appear(self.I_HONOR_BLUE):
                self._honor_mystery_amulet(con.mystery_amulet)
                mystery_bought = True
            if not black_bought and con.black_daruma_scrap and self.appear(self.I_HONOR_BLACK):
                self._honor_black_daruma_scrap(con.black_daruma_scrap)
                black_bought = True

            # 如果所有需要购买的物品都已购买完成
            if (not con.mystery_amulet or mystery_bought) and (not con.black_daruma_scrap or black_bought):
                logger.info('All honor items processed')
                break
            # 如果滑动次数过多，避免无限循环
            if swipe_count >= max_swipes:
                break
            # 如果滑动到底了
            if self.appear(self.I_SP_SWIPE_CHECK):
                break

            # 向下滑动寻找商品
            if self.swipe(self.S_SP_DOWN, interval=2):
                swipe_count += 1
                time.sleep(2)

    def _honor_mystery_amulet(self, enable: bool=False):
        logger.hr('Buy mystery amulet', 3)
        if not enable:
            logger.info('Buy mystery amulet is disabled')
            return

        # 检查剩余数量
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
        # 使用动态位置点击购买
        self.appear_then_click(self.I_HONOR_BLUE)
        time.sleep(1)

    def _honor_black_daruma_scrap(self, enable: bool=False):
        logger.hr('Buy black daruma scrap', 3)
        if not enable:
            logger.info('Buy black daruma scrap is disabled')
            return

        # 检查剩余数量
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
        # 使用动态位置点击购买
        self.buy_more(self.I_HONOR_BLACK)
        time.sleep(0.5)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = Honor(c, d)

    t.execute_honor()

