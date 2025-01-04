# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep

import re
from datetime import time, datetime, timedelta

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_summon, page_guild, page_mall, page_friends
from tasks.DailyTrifles.config import SummonType
from tasks.DailyTrifles.assets import DailyTriflesAssets
from tasks.Component.Summon.summon import Summon

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer


class ScriptTask(GameUi, Summon, DailyTriflesAssets):

    def run(self):
        con = self.config.daily_trifles.trifles_config
        # 每日召唤
        if con.one_summon:
            self.run_one_summon()
        if con.guild_wish:
            pass
        # 友情点
        if con.friend_love:
            self.run_friend_love()
        # 吉闻
        if con.luck_msg:
            self.run_luck_msg()
        # 商店签到
        if con.store_sign:
            self.run_store_sign()

        self.set_next_run('DailyTrifles', success=True, finish=False)
        raise TaskEnd('DailyTrifles')

    def run_one_summon(self):
        self.ui_get_current_page()
        self.ui_goto(page_summon)
        if self.config.daily_trifles.trifles_config.summon_type == SummonType.default:
            self.summon_one()
        elif self.config.daily_trifles.trifles_config.summon_type == SummonType.recall:
            self.summon_recall()
        self.back_summon_main()

    def summon_recall(self):
        """
        确保在召唤界面,每日召唤一次
        召唤结束后回到 召唤主界面
        :return:
        """
        list = [self.O_SELECT_SM2, self.O_SELECT_SM3, self.O_SELECT_SM4]
        count = 0
        while True:
            count += 1

            for i in range(len(list)):
                sleep(1)
                self.ui_get_current_page()
                self.ui_goto(page_main)
                self.ui_get_current_page()
                self.ui_goto(page_summon)
                self.appear_then_click(self.I_UI_BACK_RED, interval=1)
                x, y = list[i].coord()
                self.device.click(x, y)
                sleep(1)
                self.screenshot()
                if self.appear(self.I_RECALL_TICKET):
                    break
                logger.info("Select preset group RECALL")

            self.screenshot()
            if self.appear(self.I_RECALL_TICKET):
                break
            if count >= 3:
                self.config.notifier.push(title='今忆召唤抽卡失败', content='每日任务,今忆召唤抽卡失败!!!')
                return

        logger.info('Summon one RECALL')
        self.wait_until_appear(self.I_RECALL_TICKET)
        while True:
            ticket_info = self.O_RECALL_TICKET_AREA.ocr(self.device.image)
            # 处理 None 和空字符串
            if ticket_info is None or ticket_info == '':
                ticket_info = 0
            else:
                # 使用正则表达式提取字符串中的数字
                match = re.search(r'\d+', ticket_info)
                if match:
                    ticket_info = int(match.group())
                else:
                    logger.warning(f'Invalid ticket_info value: {ticket_info}, expected a numeric string')
                    ticket_info = 0  # 将无效值设置为默认值 0
            if ticket_info <= 0:
                logger.warning('There is no any one RECALL ticket')
                return
            # 某些情况下滑动异常
            self.S_RANDOM_SWIPE_1.name = 'S_RANDOM_SWIPE'
            self.S_RANDOM_SWIPE_2.name = 'S_RANDOM_SWIPE'
            self.S_RANDOM_SWIPE_3.name = 'S_RANDOM_SWIPE'
            self.S_RANDOM_SWIPE_4.name = 'S_RANDOM_SWIPE'
            while 1:
                self.screenshot()
                if self.appear(self.I_RECALL_ONE_TICKET):
                    break
                if self.appear_then_click(self.I_RECALL_TICKET, interval=1):
                    continue

            # 画一张票
            sleep(1)
            while 1:
                self.screenshot()
                if self.appear(self.I_RECALL_SM_CONFIRM, interval=0.6):
                    self.ui_click_until_disappear(self.I_RECALL_SM_CONFIRM)
                    break
                if self.appear(self.I_SM_CONFIRM_2, interval=0.6):
                    self.ui_click_until_disappear(self.I_SM_CONFIRM_2)
                    break
                if self.appear(self.I_RECALL_ONE_TICKET, interval=1):
                    # 某些时候会点击到 “语言召唤”
                    if self.appear_then_click(self.I_UI_CANCEL, interval=0.8):
                        continue
                    self.summon()
                    continue
            logger.info('Summon one success')

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
                logger.info('Get reward of friend love')
                break
            if check_timer.reached():
                logger.warning('There is no any love')
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
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1):
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

    def run_store_sign(self):
        self.ui_get_current_page()
        self.ui_goto(page_mall, confirm_wait=3)

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
            self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_MALL)
            self.ui_get_current_page()
            self.ui_goto(page_main)
            return

        if self.ui_get_reward(self.I_GIFT_SIGN, click_interval=2.5):
            logger.info('Get reward of gift sign')

        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_MALL)
        self.ui_get_current_page()
        self.ui_goto(page_main)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas2')
    d = Device(c)
    t = ScriptTask(c, d)
    # t.run()
    t.run_one_summon()
    # t.run_store_sign()
