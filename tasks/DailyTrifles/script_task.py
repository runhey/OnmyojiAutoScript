# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_summon, page_guild, page_mall, page_friends
from tasks.DailyTrifles.config import DailyTriflesConfig
from tasks.DailyTrifles.assets import DailyTriflesAssets
from tasks.Component.Summon.summon import Summon

from module.logger import logger
from module.exception import TaskEnd


class ScriptTask(GameUi, Summon, DailyTriflesAssets):

    def run(self):
        con = self.config.daily_trifles.trifles_config
        if con.one_summon:
            self.run_one_summon()
        if con.guild_wish:
            pass
        if con.friend_love:
            self.run_friend_love()
        if con.store_sign:
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

    def run_friend_love(self):
        self.ui_get_current_page()
        self.ui_goto(page_friends)
        while 1:
            self.screenshot()
            if self.appear(self.I_L_LOVE):
                break
            if self.appear_then_click(self.I_L_FRIENDS, interval=1):
                continue
        logger.info('Friend love')
        sleep(0.5)
        self.screenshot()
        if not self.appear(self.I_L_COLLECT):
            logger.warning('There is no any love')
            self.ui_click(self.I_UI_BACK_RED, self.I_CHECK_MAIN)
            return
        if self.ui_get_reward(self.I_L_COLLECT):
            logger.info('Get reward of friend love')

        self.ui_click(self.I_UI_BACK_RED, self.I_CHECK_MAIN)

    def run_store_sign(self):
        self.ui_get_current_page()
        self.ui_goto(page_mall, confirm_wait=3)

        start_time = datetime.now()
        found_gift_recommend = False

        while datetime.now() - start_time < timedelta(seconds=5):
            self.screenshot()
            if self.appear(self.I_GIFT_RECOMMEND):
                self.appear_then_click(self.I_GIFT_RECOMMEND, interval=1)
                found_gift_recommend = True
                break
            if self.appear_then_click(self.I_ROOM_GIFT, interval=1):
                continue

        if not found_gift_recommend:
            logger.warning('I_ROOM_GIFT not found within 5 seconds')
            self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_MALL)
            self.ui_get_current_page()
            self.ui_goto(page_main)
            return

        logger.info('Enter store sign')
        sleep(1)  # 等个动画
        self.screenshot()
        if not self.appear(self.I_GIFT_SIGN):
            logger.warning('There is no gift sign')
            self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_MALL)
            self.ui_get_current_page()
            self.ui_goto(page_main)
            return

        if self.ui_get_reward(self.I_GIFT_SIGN):
            logger.info('Get reward of gift sign')

        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_MALL)
        self.ui_get_current_page()
        self.ui_goto(page_main)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from memory_profiler import profile

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run_store_sign()
