# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import random

from tasks.Component.Summon.assets import SummonAssets
from tasks.base_task import BaseTask
from module.logger import logger


class Summon(BaseTask, SummonAssets):


    def summon(self):
        """
        召唤, 就是随机画一个， 划线
        :return:
        """
        self.screenshot()
        random_swipe = random.randint(0, 3)
        target_swipe = None
        match random_swipe:
            case 0: target_swipe = self.S_RANDOM_SWIPE_1
            case 1: target_swipe = self.S_RANDOM_SWIPE_2
            case 2: target_swipe = self.S_RANDOM_SWIPE_3
            case 3: target_swipe = self.S_RANDOM_SWIPE_4
            case _: target_swipe = self.S_RANDOM_SWIPE_1
        self.swipe(target_swipe, interval=0.5)



    def summon_one(self):
        """
        确保在召唤界面,每日召唤一次
        召唤结束后回到 召唤主界面
        :return:
        """
        logger.info('Summon one')
        self.wait_until_appear(self.I_BLUE_TICKET)
        ticket_info = self.O_ONE_TICKET.ocr(self.device.image)
        if '1' not in ticket_info:
            logger.warning('There is no any one blue ticket')
            return
        while 1:
            self.screenshot()

            if self.appear_then_click(self.I_ONE_TICKET):
                break
            if self.appear_then_click(self.I_BLUE_TICKET, interval=1):
                continue
        time.sleep(1)
        self.summon()
        self.wait_until_appear(self.I_SM_CONFIRM)
        while 1:
            self.screenshot()
            if not self.appear(self.I_SM_CONFIRM):
                break
            if self.appear_then_click(self.I_SM_CONFIRM):
                continue


    def back_summon_main(self):
        """
        返回召唤主界面
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear(self.I_BLUE_TICKET):
                break
            if self.appear_then_click(self.I_UI_BACK_BLUE):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW):
                continue

