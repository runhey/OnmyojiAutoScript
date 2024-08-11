# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from module.logger import logger

from tasks.GameUi.page import page_main, page_guild
from tasks.RichMan.mall.friendship_points import FriendshipPoints
from tasks.RichMan.config import Charisma as CharismaConfig


class Charisma(FriendshipPoints):

    def execute_charisma(self, con: CharismaConfig = None):
        if not con:
            logger.info('Charisma is not enable')
            con = self.config.rich_man.charisma
        if not con.enable:
            logger.info('Charisma is not enable')
            return
        self._enter_charisma()

        # 开始
        # 黑色碎片
        if con.black_daruma_scrap:
            self.buy_mall_more(buy_button=self.I_CH_BLACK, remain_number=True,
                               money_ocr=self.O_MALL_RESOURCE_5,
                               buy_number=2, buy_max=2, buy_money=320)
        # 蓝票
        if con.mystery_amulet:
            self.buy_mall_one(buy_button=self.I_CH_BLUE, buy_check=self.I_CH_CHECK_BLUE,
                              money_ocr=self.O_MALL_RESOURCE_5, buy_money=400)




if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = Charisma(c, d)

