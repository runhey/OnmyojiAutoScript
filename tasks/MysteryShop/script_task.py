# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
from time import sleep
from datetime import timedelta, datetime, time
from cached_property import cached_property

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.page import page_main, page_mall
from tasks.GameUi.game_ui import GameUi
from tasks.RichMan.mall.friendship_points import FriendshipPoints
from tasks.MysteryShop.config import MysteryShop, ShopConfig, ShareConfig
from tasks.MysteryShop.assets import MysteryShopAssets
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.GeneralInvite.config_invite import InviteConfig, InviteNumber, FindMode

class ScriptTask(FriendshipPoints, MysteryShopAssets, GeneralInvite):

    def run(self):
        day_of_week = self.start_time.weekday()
        if day_of_week != 2 and day_of_week != 5:
            logger.warning('Today is not MysteryShop day')
            self.next_time(False)
        self.ui_get_current_page()
        self.ui_goto(page_mall)
        self.ui_click(self.I_ME_ENTER, self.I_MS_SHARE)
        logger.info('Enter MysteryShop')
        con = self.config.mystery_shop
        self.share(con.share_config)
        while 1:
            self.run_shop(con.shop_config)
            if not self.next_one():
                break
        self.shop_reward()
        logger.info('Exit MysteryShop')
        self.back_mall()


        self.next_time(True)

    def next_one(self):
        """
        切换下一个好友的商店
        :return:
        """
        self.screenshot()
        if not self.appear(self.I_MS_NEXT):
            sleep(0.5)
            self.screenshot()
            if self.appear(self.I_MS_NEXT):
                pass
            else:
                logger.info('No next friend')
                return False

        own_page = self.appear(self.I_MS_SHARE)
        if own_page:
            while 1:
                self.screenshot()
                if not self.appear(self.I_MS_SHARE):
                    break
                if self.appear_then_click(self.I_MS_NEXT, interval=1):
                    continue
            logger.info('Switch to next friend')
            return True

        present_friend = self.O_MS_FRIEND.ocr(self.device.image)
        while 1:
            self.screenshot()
            next_friend = self.O_MS_FRIEND.ocr(self.device.image)
            if present_friend != next_friend:
                break
            if self.appear_then_click(self.I_MS_NEXT, interval=2.5):
                continue

        logger.info('Switch to next friend')
        return True



    def run_shop(self, shop_config: ShopConfig = None):
        """
        在当前的商店进行购买
        :return:
        """
        if shop_config.mystery_amulet:
            while self.buy_mall_one(buy_button=self.I_MS_BLUE, buy_check=self.I_MS_CHECK_BLUE,
                                    money_ocr=self.O_MALL_RESOURCE_5, buy_money=85):
                pass
        if shop_config.black_daruma_scrap:
            while self.buy_mall_one(buy_button=self.I_MS_BLACK, buy_check=self.I_MS_CHECK_BLACK,
                                    money_ocr=self.O_MALL_RESOURCE_5, buy_money=60):
                pass
        if shop_config.shop_kaiko_3:
            while self.buy_mall_one(buy_button=self.I_MS_TAIKO_3, buy_check=self.I_MS_CHECK_TAIKO_3,
                                    money_ocr=self.O_MALL_RESOURCE_5, buy_money=45):
                pass
        if shop_config.shop_kaiko_4:
            while self.buy_mall_one(buy_button=self.I_MS_TAIKO_4, buy_check=self.I_MS_CHECK_TAIKO_4,
                                    money_ocr=self.O_MALL_RESOURCE_5, buy_money=80):
                pass

    def share(self, share_config: ShareConfig = None):
        logger.hr('Share', 3)
        if not share_config.enable:
            logger.info('Share is disabled')
            return

        if share_config.share_friend_1 == '':
            logger.info('Share friend is empty')
            return
        self.ui_click(self.I_MS_SHARE, self.I_INVITE_ENSURE)
        if not self.invite_friend(share_config.share_friend_1):
            logger.warning(f'Share friend 1 {share_config.share_friend_1} is not exist')

        if share_config.share_friend_2 != '':
            self.ui_click(self.I_MS_SHARE, self.I_INVITE_ENSURE)
            if not self.invite_friend(share_config.share_friend_2):
                logger.warning(f'Share friend 2 {share_config.share_friend_2} is not exist')

        if share_config.share_friend_3 != '':
            self.ui_click(self.I_MS_SHARE, self.I_INVITE_ENSURE)
            if not self.invite_friend(share_config.share_friend_3):
                logger.warning(f'Share friend 3 {share_config.share_friend_3} is not exist')

        if share_config.share_friend_4 != '':
            self.ui_click(self.I_MS_SHARE, self.I_INVITE_ENSURE)
            if not self.invite_friend(share_config.share_friend_4):
                logger.warning(f'Share friend 4 {share_config.share_friend_4} is not exist')

        if share_config.share_friend_5 != '':
            self.ui_click(self.I_MS_SHARE, self.I_INVITE_ENSURE)
            if not self.invite_friend(share_config.share_friend_5):
                logger.warning(f'Share friend 5 {share_config.share_friend_5} is not exist')

    def invite_friend(self, name: str = None, find_mode: FindMode = FindMode.AUTO_FIND) -> bool:
        """
        重写
        :param find_mode:
        :param name:
        :return:
        """
        def select(name: str) -> bool:
            selected = False
            sleep(1)
            if not selected:
                if self.detect_select(name):
                    selected = True
            sleep(1)
            if not selected:
                if self.detect_select(name):
                    selected = True
            return selected

        selected = False
        self.ui_click_until_disappear(self.I_FLAG_1_OFF)
        logger.info(f'Now find friend in same server')
        selected = select(name)

        if not selected:
            self.ui_click_until_disappear(self.I_FLAG_2_OFF)
            logger.info(f'Now find friend in different server')
            selected = select(name)

        self.ui_click_until_disappear(self.I_INVITE_ENSURE)
        if selected:
            logger.info('Click invite ensure')
            return True
        else:
            logger.warning('Friend not found')
            return False

    def shop_reward(self):
        logger.info('Shop reward')
        self.screenshot()
        number = self.O_MS_RECORDS.ocr(self.device.image)
        if not isinstance(number, int):
            logger.warning('No shop reward')
            return
        logger.info(f'Shop reward {number}')
        if number >= 3:
            self.ui_get_reward(self.I_MS_REWARD_3)
            sleep(0.5)
        if number >= 5:
            self.ui_get_reward(self.I_MS_REWARD_5)
            sleep(0.5)
        if number >= 10:
            self.ui_get_reward(self.I_MS_REWARD_10)
            sleep(0.5)
        logger.info('Shop reward done')

    def next_time(self, success: bool = True):
        """
        重写
        """
        target_time: time = self.config.mystery_shop.shop_config.time_of_mystery
        target_time: timedelta = timedelta(hours=target_time.hour, minutes=target_time.minute,
                                           seconds=target_time.second)
        if target_time == time(hour=0, minute=0, second=0):
            if success:
                self.set_next_run(task='MysteryShop', success=True, finish=True)
            else:
                self.set_next_run(task='MysteryShop', success=False, finish=True)
            raise TaskEnd('MysteryShop')
        now = datetime.now()
        day_of_week = now.weekday()
        now_datetime = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if 2 <= day_of_week <= 4:
            # 如果现在是周三和周五之间，那就设定下一次为这周六（hour=0, minute=0, second=0）+ target_time
            next_time = now_datetime + timedelta(days=5 - day_of_week) + target_time
        elif 5 <= day_of_week <= 6 or 0 <= day_of_week <= 1:
            # 如果现在是周六和周一之间，那就设定下一次为下周三（hour=0, minute=0, second=0）+ target_time
            next_time = now_datetime + timedelta(days=6 - day_of_week + 3) + target_time
        else:
            next_time = now_datetime + timedelta(days=2 - day_of_week) + target_time
            logger.warning('Now is not in the time of mystery shop')
        self.set_next_run(task='MysteryShop', target=next_time)
        raise TaskEnd('MysteryShop')


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    # t.run_shop(t.config.mystery_shop.shop_config)
    t.run()

