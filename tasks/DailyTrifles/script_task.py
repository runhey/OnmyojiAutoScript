# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import copy
from time import sleep
from datetime import time, datetime, timedelta

from exceptiongroup import catch
from winerror import NOERROR

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_summon, page_guild, page_mall, page_friends
from tasks.DailyTrifles.config import DailyTriflesConfig
from tasks.DailyTrifles.assets import DailyTriflesAssets
from tasks.Component.Summon.summon import Summon

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer


class ScriptTask(GameUi, Summon, DailyTriflesAssets):

    def run(self):
        con = self.config.daily_trifles.trifles_config
        if con.one_summon:
            self.run_one_summon()
        if con.guild_wish:
            pass
        if con.friend_love:
            self.run_friend_love()
        if con.luck_msg:
            self.run_luck_msg()
        if con.store_sign or con.buy_sushi_count > 0:
            self.run_store_sign()
        self.set_next_run('DailyTrifles', success=True, finish=False)
        raise TaskEnd('DailyTrifles')

    def run_one_summon(self):
        self.ui_get_current_page()
        self.ui_goto(page_summon)
        self.summon_one()
        self.back_summon_main()

    def run_guild_wish(self):
        pass

    def run_luck_msg(self):
        self.ui_get_current_page()
        self.ui_goto(page_friends)
        while 1:
            self.screenshot()
            if self.appear(self.I_LUCK_TITLE):
                break
            if self.appear_then_click(self.I_LUCK_MSG, interval=1):
                continue
        logger.info('Start luck msg')
        check_timer = Timer(2)
        check_timer.start()
        while 1:
            self.screenshot()

            if self.appear_then_click(self.I_CLICK_BLESS, interval=1):
                continue
            if self.appear_then_click(self.I_ONE_CLICK_BLESS, interval=1):
                continue
            if self.ui_reward_appear_click():
                logger.info('Get reward of luck msg')
                break
            if check_timer.reached():
                logger.warning('There is no any luck msg')
                break

        self.ui_click(self.I_UI_BACK_RED, self.I_CHECK_MAIN)

    def run_friend_love(self):
        self.ui_get_current_page()
        self.ui_goto(page_friends)
        while 1:
            self.screenshot()
            if self.appear(self.I_L_LOVE):
                break
            if self.appear_then_click(self.I_L_FRIENDS, interval=1):
                continue
        logger.info('Start friend love')
        check_timer = Timer(2)
        check_timer.start()
        while 1:
            self.screenshot()

            if self.appear_then_click(self.I_L_COLLECT, interval=1):
                continue
            if self.ui_reward_appear_click():
                logger.info('Get reward of friend love')
                break
            if check_timer.reached():
                logger.warning('There is no any love')
                break

        self.ui_click(self.I_UI_BACK_RED, self.I_CHECK_MAIN)

    def run_store(self):
        self.ui_get_current_page()
        self.ui_goto(page_mall, confirm_wait=3)

        if self.config.daily_trifles.trifles_config.store_sign:
            self.run_store_sign()
        if self.config.daily_trifles.trifles_config.buy_sushi_count > 0:
            self.run_buy_sushi()

        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_MALL)
        self.ui_get_current_page()
        self.ui_goto(page_main)

    def run_store_sign(self):

        while 1:
            self.screenshot()
            if self.appear(self.I_GIFT_RECOMMEND):
                break
            if self.appear_then_click(self.I_ROOM_GIFT, interval=1):
                continue
        self.screenshot()
        self.appear_then_click(self.I_GIFT_RECOMMEND, interval=1)
        logger.info('Enter store sign')
        sleep(1)  # 等个动画
        self.screenshot()
        if not self.appear(self.I_GIFT_SIGN):
            logger.warning('There is no gift sign')
            return

        if self.ui_get_reward(self.I_GIFT_SIGN, click_interval=2.5):
            logger.info('Get reward of gift sign')

    def run_buy_sushi(self):

        # 进入Special
        while 1:
            from tasks.RichMan.assets import RichManAssets
            self.screenshot()
            if self.appear(RichManAssets.I_SIDE_CHECK_SPECIAL):
                break
            if self.appear_then_click(RichManAssets.I_MALL_SUNDRY, interval=1):
                continue
            if self.appear_then_click(RichManAssets.I_SIDE_SURE_SPECIAL, interval=1):
                continue

        def detect_buy_count(base_element) -> (int, int):
            # 返回count,price
            MAX_PRICE = 9999
            MAX_COUNT = 9999
            roi = copy.deepcopy(base_element.roi_front)
            roi[0] = roi[0] + roi[2]
            roi[1] = roi[1] + roi[3] - 30
            roi[2] = 60
            roi[3] = 30
            self.O_STORE_SUSHI_PRICE.roi = roi
            _price = self.O_STORE_SUSHI_PRICE.detect_text(self.device.image)
            # 保守策略，避免OCR错误购买
            try:
                _price = int(_price)
            except Exception as e:
                _price = MAX_PRICE

            if _price < 60:
                return 0, MAX_PRICE
            _count = (_price - 60) / 20
            return _count, _price

        roi = None
        # 购买体力
        while 1:
            self.screenshot()
            # count, price = detect_buy_count(roi)
            # if count >= self.config.model.daily_trifles.trifles_config.buy_sushi_count:
            #     break
            if self.appear(self.I_STORE_COST_TYPE_JADE):
                count, price = detect_buy_count(self.I_STORE_COST_TYPE_JADE)
                if count >= self.config.daily_trifles.trifles_config.buy_sushi_count:
                    break
                self.ui_click_until_disappear(self.I_STORE_COST_TYPE_JADE, interval=2)
                logger.info(f"Buy Sushi With {price} Jade")
                continue

            if self.appear(self.I_SPECIAL_SUSHI):
                # 此处确定当前购买体力所需勾玉数量的位置,用于后续识别
                count, price = detect_buy_count(self.I_SPECIAL_SUSHI)
                if count >= self.config.daily_trifles.trifles_config.buy_sushi_count:
                    break
                self.ui_click(self.I_SPECIAL_SUSHI, stop=self.I_STORE_COST_TYPE_JADE, interval=2)
                continue
        return


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run_store()
