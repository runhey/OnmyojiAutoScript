# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from module.logger import logger

from tasks.GameUi.page import page_main, page_guild
from tasks.GameUi.game_ui import GameUi
from tasks.Component.Buy.buy import Buy
from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import MedalRoom
from tasks.RichMan.mall.friendship_points import FriendshipPoints


class Medal(FriendshipPoints):

    def execute_medal(self, con: MedalRoom = None):
        if not con:
            con = self.config.rich_man.medal_room
        if not con.enable:
            logger.info('Medal is not enable')
            return
        self._enter_medal()

        # 黑蛋
        if con.black_daruma:
            self.buy_mall_one(buy_button=self.I_ME_BLACK, buy_check=self.I_ME_CHECK_BLACK,
                              money_ocr=self.O_MALL_RESOURCE_3, buy_money=480)
        # 蓝票
        if con.mystery_amulet:
            self.buy_mall_one(buy_button=self.I_ME_BLUE, buy_check=self.I_ME_CHECK_BLUE,
                              money_ocr=self.O_MALL_RESOURCE_3, buy_money=180)
        # 体力100
        if con.ap_100:
            self.buy_mall_one(buy_button=self.I_ME_AP, buy_check=self.I_ME_CHECK_AP,
                              money_ocr=self.O_MALL_RESOURCE_3, buy_money=120)
        # 随机御魂
        if con.random_soul:
            pass
            # self.buy_mall_one(buy_button=self.I_ME_SOULS, buy_check=self.I_ME_CHECK_SOULS,
            #                   money_ocr=self.O_MALL_RESOURCE_5, buy_money=320)
        # 两颗白蛋
        if con.white_daruma:
            self.buy_mall_more(buy_button=self.I_ME_WHITE, remain_number=True, money_ocr=self.O_MALL_RESOURCE_3,
                               buy_number=2, buy_max=2, buy_money=100)
        # 十张挑战券
        if con.challenge_pass:
            self.buy_mall_more(buy_button=self.I_ME_CHALLENGE_PASS, remain_number=True, money_ocr=self.O_MALL_RESOURCE_3,
                               buy_number=con.challenge_pass, buy_max=10, buy_money=30)
        # 红蛋
        if con.red_daruma:
            self.buy_mall_more(buy_button=self.I_ME_RED, remain_number=False,
                               money_ocr=self.O_MALL_RESOURCE_3,
                               buy_number=con.red_daruma, buy_max=99, buy_money=30)
        # 破碎的咒符
        if con.broken_amulet:
            self.buy_mall_more(buy_button=self.I_ME_BROKEN, remain_number=False,
                               money_ocr=self.O_MALL_RESOURCE_3,
                               buy_number=con.broken_amulet, buy_max=99, buy_money=20)

        time.sleep(1)



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = Medal(c, d)

    t.execute_medal()

