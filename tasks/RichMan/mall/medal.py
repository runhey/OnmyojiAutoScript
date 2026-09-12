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

        # 记录识别失败的商品，用于事后核对是否为售罄
        not_found = []

        # 黑蛋
        if con.black_daruma:
            self.screenshot()
            if self.appear(self.I_ME_BLACK):
                self.buy_mall_one(buy_button=self.I_ME_BLACK, buy_check=self.I_ME_CHECK_BLACK,
                                  money_ocr=self.O_MALL_RESOURCE_3, buy_money=480)
            else:
                not_found.append('black_daruma')
        # 蓝票
        if con.mystery_amulet:
            self.screenshot()
            if self.appear(self.I_ME_BLUE):
                self.buy_mall_one(buy_button=self.I_ME_BLUE, buy_check=self.I_ME_CHECK_BLUE,
                                  money_ocr=self.O_MALL_RESOURCE_3, buy_money=180)
            else:
                not_found.append('mystery_amulet')
        # 体力100
        if con.ap_100:
            self.screenshot()
            if self.appear(self.I_ME_AP):
                self.buy_mall_one(buy_button=self.I_ME_AP, buy_check=self.I_ME_CHECK_AP,
                                  money_ocr=self.O_MALL_RESOURCE_3, buy_money=120)
            else:
                not_found.append('ap_100')
        # 随机御魂
        if con.random_soul:
            self.screenshot()
            if self.appear(self.I_ME_SOULS):
                self.buy_mall_one(buy_button=self.I_ME_SOULS, buy_check=self.I_ME_CHECK_SOULS,
                                  money_ocr=self.O_MALL_RESOURCE_3, buy_money=320)
            else:
                not_found.append('random_soul')
        # 两颗白蛋
        if con.white_daruma:
            self.screenshot()
            if self.appear(self.I_ME_WHITE):
                self.buy_mall_more(buy_button=self.I_ME_WHITE, remain_number=True, money_ocr=self.I_MALL_RESOURCE_MEDAL.build_mall_resource_ocr(self.device.image),
                                   buy_number=2, buy_max=2, buy_money=100)
            else:
                not_found.append('white_daruma')
        # 十张挑战券
        if con.challenge_pass:
            self.screenshot()
            if self.appear(self.I_ME_CHALLENGE_PASS):
                self.buy_mall_more(buy_button=self.I_ME_CHALLENGE_PASS, remain_number=True, money_ocr=self.I_MALL_RESOURCE_MEDAL.build_mall_resource_ocr(self.device.image),
                                   buy_number=con.challenge_pass, buy_max=10, buy_money=30)
            else:
                not_found.append('challenge_pass')
        # 红蛋
        if con.red_daruma:
            self.screenshot()
            if self.appear(self.I_ME_RED):
                self.buy_mall_more(buy_button=self.I_ME_RED, remain_number=False,
                                   money_ocr=self.I_MALL_RESOURCE_MEDAL.build_mall_resource_ocr(self.device.image),
                                   buy_number=con.red_daruma, buy_max=99, buy_money=30)
            else:
                not_found.append('red_daruma')
        # 破碎的咒符
        if con.broken_amulet:
            self.screenshot()
            if self.appear(self.I_ME_BROKEN):
                self.buy_mall_more(buy_button=self.I_ME_BROKEN, remain_number=False,
                                   money_ocr=self.I_MALL_RESOURCE_MEDAL.build_mall_resource_ocr(self.device.image),
                                   buy_number=con.broken_amulet, buy_max=99, buy_money=20)
            else:
                not_found.append('broken_amulet')

        # 有识别失败的商品：核对售罄数量，确认失败是否为"商品售罄"（正常情况），而非页面异常。
        # 注意：页面上的售罄标签可能包含未配置购买的商品，因此用 >= 而非 ==，避免误报。
        if not_found:
            self.screenshot()
            soldout_count = self.count_soldout()
            if soldout_count >= len(not_found):
                logger.info(f'Medal: {len(not_found)} item(s) not detected, sold out count is {soldout_count}, '
                            f'the not-detected items are sold out, skip normally')
            else:
                logger.warning(f'Medal: {len(not_found)} item(s) not detected, but sold out count is only {soldout_count}, '
                               f'some items may not be sold out, page may be abnormal, please check manually')

        time.sleep(1)

    def count_soldout(self) -> int:
        """
        统计勋章商店页面中"售罄"标签的数量。
        通过 OCR 检测商品区域内含"售"字的文本块（售罄标签），用于核对识别失败的商品是否均为售罄。
        需要先调用 screenshot 保证 self.device.image 为最新画面。
        :return: 售罄标签数量
        """
        results = self.O_SOLD_OUT.detect_and_ocr(self.device.image, logDisplay=False)
        count = sum(1 for r in results if '售' in r.ocr_text)
        logger.info(f'Medal sold out count: {count}')
        return count


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = Medal(c, d)

    t.execute_medal()

