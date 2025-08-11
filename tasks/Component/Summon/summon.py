# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import random

from tasks.Component.Summon.assets import SummonAssets
from tasks.base_task import BaseTask
from module.logger import logger
import re

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

    def summon_mystery_pattern(self):
        """
        每月神秘图案
        :return:
        """
        # 目前只测试了7月的，其他月份的我是根据截图描的，可能需要调整
        # 一月
        jan = [(400, 119), (406, 525), (862, 123), (864, 521), (402, 121)]
        # 二月、八月
        febAndAug = [(450, 105), (453, 525)]
        # 三月、九月
        marAndSep = [(390, 304), (886, 302)]
        # 四月、十月
        aprAndOct = [(402, 526), (862, 125)]
        # 五月、十一月
        mayAndNov = [(414, 207), (648, 550), (870, 209)]
        # 六月、十二月
        junAndDec = [(413, 138), (850, 133), (856, 226), (415, 239), (416, 140), (531, 136), (535, 590), (791, 586),
                     (760, 131)]
        # 七月
        jul = [(418, 124), (421, 504), (853, 511), (855, 128)]
        # 月份字典
        month_dict = {
            1: jan,
            2: febAndAug,
            3: marAndSep,
            4: aprAndOct,
            5: mayAndNov,
            6: junAndDec,
            7: jul,
            8: febAndAug,
            9: marAndSep,
            10: aprAndOct,
            11: mayAndNov,
            12: junAndDec
        }
        # 获取当前月份
        current_month = time.localtime().tm_mon
        current_pattern = month_dict.get(current_month, None)
        if current_pattern is None:
            logger.warning(f'不支持的月份: {current_month}')
            return
        self.screenshot()
        self.device.draw_adb(current_pattern)



    def summon_one(self,draw_mystery_pattern=False):
        """
        确保在召唤界面,每日召唤一次
        召唤结束后回到 召唤主界面
        :return:
        """
        logger.info('Summon one')
        self.wait_until_appear(self.I_BLUE_TICKET)
        while True:
            ticket_info = self.O_ONE_TICKET.ocr(self.device.image)
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
                logger.warning('There is no any one blue ticket')
                return
            # 某些情况下滑动异常
            self.S_RANDOM_SWIPE_1.name = 'S_RANDOM_SWIPE'
            self.S_RANDOM_SWIPE_2.name = 'S_RANDOM_SWIPE'
            self.S_RANDOM_SWIPE_3.name = 'S_RANDOM_SWIPE'
            self.S_RANDOM_SWIPE_4.name = 'S_RANDOM_SWIPE'
            while 1:
                self.screenshot()
                if self.appear(self.I_ONE_TICKET):
                    break
                if self.appear_then_click(self.I_BLUE_TICKET, interval=1):
                    continue

            # 画一张票
            time.sleep(0.5)
            while 1:
                self.screenshot()
                if self.appear(self.I_SM_CONFIRM, interval=0.6):
                    self.ui_click_until_disappear(self.I_SM_CONFIRM)
                    break
                if self.appear(self.I_SM_CONFIRM_2, interval=0.6):
                    self.ui_click_until_disappear(self.I_SM_CONFIRM_2)
                    break
                if self.appear(self.I_ONE_TICKET, interval=1):
                    # 某些时候会点击到 “语言召唤”
                    if self.appear_then_click(self.I_UI_CANCEL, interval=0.8):
                        continue
                    if draw_mystery_pattern:
                        self.summon_mystery_pattern()
                    else:
                        self.summon()
                    continue
            logger.info('Summon one success')


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

