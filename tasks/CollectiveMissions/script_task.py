# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
import random
import re
from cached_property import cached_property
from enum import Enum
from datetime import timedelta

from module.exception import TaskEnd, RequestHumanTakeover
from module.logger import logger
from module.base.timer import Timer
from module.atom.ocr import RuleOcr

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_guild
from tasks.CollectiveMissions.assets import CollectiveMissionsAssets


class MC(str, Enum):
    BL = '契灵'
    AW1 = '觉醒一'
    AW2 = '觉醒二'
    AW3 = '觉醒三'
    GR1 = '御灵一'
    GR2 = '御灵二'
    GR3 = '御灵三'
    SO1 = '御魂一'
    SO2 = '御魂二'
    FRIEND = '结伴同行'
    UNKNOWN = '未知'
    FEED = '远远不够'  # 喂N卡

class ScriptTask(GameUi, CollectiveMissionsAssets):
    missions: list = []  # 用于记录三个的任务的种类

    @cached_property
    def rule(self) -> list:
        rule = self.config.collective_missions.missions_config.missions_rule
        rule = rule.replace(' ', '').replace('\n', '')
        # 正则表达式 分离 ">"
        rule = re.split(r'>', rule)
        mc_values_list = [member.value for member in MC]
        rule = [item for item in rule if item in mc_values_list]
        return rule

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_guild)
        rule = self.config.collective_missions.missions_config.missions_rule
        self.ui_click(self.I_CM_SHRINE, self.I_CM_CM)
        self.ui_click(self.I_CM_CM, self.I_CM_RECORDS)
        logger.info('Start to detect missions')
        # 判断今天是否已经完成了， 还是多少次数的任务
        self.screenshot()
        current, remain, total = self.O_CM_NUMBER.ocr(self.device.image)
        if current == total == 30:
            logger.warning('Today\'s missions have been completed')
            self.set_next_run(task='CollectiveMissions', success=False, finish=True)
            raise TaskEnd('CollectiveMissions')
        # 判断最优的任务是哪一个
        mission, index = self.detect_best()
        logger.info(f'Best mission is {mission}')
        logger.info(f'Best mission index is {index}')
        if mission == MC.BL:
            # 契灵单独处理
            self._bondling_fairyland(index)
        elif mission == MC.FEED:
            # 单独喂一个 N 卡
            self._feed(index)
        elif mission == MC.AW1 or mission == MC.AW2 or mission == MC.AW3 \
                or mission == MC.GR1 or mission == MC.GR2 or mission == MC.GR3:
            # 其他就捐材料
            self._donate(index)
        elif mission == MC.SO1 or mission == MC.SO2:
            # 御魂就捐御魂
            self._soul(index)

        # 退出
        while 1:
            self.screenshot()
            if self.appear(self.I_CM_SHRINE) or self.appear(self.I_CHECK_MAIN):
                break
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1):
                continue


        self.set_next_run(task='CollectiveMissions', success=True, finish=True)
        raise TaskEnd('CollectiveMissions')


    def detect_one(self, ocr_1: RuleOcr, ocr_2: RuleOcr) -> MC:
        """
        检测某一个位置是什么的任务
        :param ocr_1:
        :param ocr_2:
        :return:
        """
        self.screenshot()
        result_1 = ocr_1.ocr(self.device.image)
        result_2 = ocr_2.ocr(self.device.image)
        result_1 = result_1.replace('·', '')
        if result_1 == '结伴同行':
            return MC.FRIEND
        elif result_1 == '契灵探查':
            return MC.BL
        if result_2 == '觉醒一':
            return MC.AW1
        elif result_2 == '觉醒二':
            return MC.AW2
        elif result_2 == '觉醒三':
            return MC.AW3
        elif result_2 == '御灵一':
            return MC.GR1
        elif result_2 == '御灵二':
            return MC.GR2
        elif result_2 == '御灵三':
            return MC.GR3
        elif result_2 == '御魂一':
            return MC.SO1
        elif result_2 == '御魂二':
            return MC.SO2
        if result_1 == '远远不够':
            logger.warning(f'Ocr task name: {result_1}')
            return MC.FEED
        return MC.UNKNOWN

    def detect_best(self) -> tuple:
        """
        自动寻找最好的任务并返回，期间记录三个任务的类型
        :return: 任务类型, 0/1/2
        """
        first_class = self.detect_one(self.O_CM_1, self.O_CM_2)
        second_class = self.detect_one(self.O_CM_3, self.O_CM_4)
        third_class = self.detect_one(self.O_CM_5, self.O_CM_6)
        first_order = self.rule.index(first_class) if first_class in self.rule else 100
        second_order = self.rule.index(second_class) if second_class in self.rule else 101
        third_order = self.rule.index(third_class) if third_class in self.rule else 102
        logger.info(f'first_class: {first_class}, second_class: {second_class}, third_class: {third_class}')
        logger.info(f'first_order: {first_order}, second_order: {second_order}, third_order: {third_order}')
        if first_order < second_order and first_order < third_order:
            best_index, best_class = 0, first_class
        elif second_order < first_order and second_order < third_order:
            best_index, best_class = 1, second_class
        elif third_order < first_order and third_order < second_order:
            best_index, best_class = 2, third_class
        return best_class, best_index


    def _bondling_fairyland(self, index: int):
        """
        如果御灵已经做了那么就领取奖励
        否则将契灵之境的任务设置为当前，同时两个小时后继续执行当前的任务收菜
        :return:
        """
        def bondling_finish():
            self.screenshot()
            if self.appear(self.I_CM_REWARDS):
                return True
            return False
        if not bondling_finish():
            self.config.bondling_fairyland.scheduler.next_run = self.start_time
            if not self.config.bondling_fairyland.scheduler.enable:
                logger.error('The scheduler of bondling_fairyland is not enable')
                logger.error('Please enable it in config file')
                raise RequestHumanTakeover
            self.set_next_run(task='CollectiveMissions', success=True, finish=True, target=self.start_time + timedelta(hours=2))
            return True
        # 领取奖励
        logger.info('Start to collect bondling rewards')
        check_timer = Timer(3)
        check_timer.start()
        while 1:
            self.screenshot()
            if self.ui_reward_appear_click(True):
                check_timer.reset()
                continue
            if self.appear_then_click(self.I_CM_REWARDS, interval=1):
                check_timer.reset()
                continue
            if check_timer.reached():
                break
        logger.info('Finish to collect bondling rewards')

    def _donate(self, index: int):
        """
        捐赠材料
        :param index: 0, 1, 2 三个任务的位置
        :return:
        """
        match_click = {
            0: self.C_CM_1,
            1: self.C_CM_2,
            2: self.C_CM_3,
        }
        while 1:
            self.screenshot()
            if self.appear(self.I_CM_PRESENT):
                break
            if self.click(match_click[index], interval=1.5):
                continue
        # 开始捐材料
        logger.info('Start to donate')
        # 判断哪一个的材料最多
        self.screenshot()
        max_index = 0
        max_number = 0
        for i, ocr in enumerate([self.O_CM_1_MATTER, self.O_CM_2_MATTER,
                                 self.O_CM_3_MATTER, self.O_CM_4_MATTER]):
            curr, remain, total = ocr.ocr(self.device.image)
            if total > max_number:
                max_number = total
                max_index = i
        if max_number <= 30:
            logger.info('The number of all matter is less than 30')
            logger.info('Please check your game resolution')
            raise RequestHumanTakeover

        match_swipe = {
            0: self.S_CM_MATTER_1,
            1: self.S_CM_MATTER_2,
            2: self.S_CM_MATTER_3,
            3: self.S_CM_MATTER_4,
        }
        match_image = {
            0: self.I_CM_ADD_1,
            1: self.I_CM_ADD_2,
            2: self.I_CM_ADD_3,
            3: self.I_CM_ADD_4,
        }
        # 滑动到最多的材料
        random_click = [self.I_CM_ADD_1, self.I_CM_ADD_2, self.I_CM_ADD_3, self.I_CM_ADD_4]
        window_control = self.config.script.device.control_method == 'window_message'
        swipe_count = 0
        click_count = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_CM_MATTER):
                break
            if not window_control and self.swipe(match_swipe[max_index], interval=2.5):
                swipe_count += 1
                time.sleep(1.5)
                continue

            # 为什么使用window_message无法滑动
            if window_control and click_count > 30:
                logger.info('Swipe to the most matter failed')
                logger.info('Please check your game resolution')
                break
            if window_control and self.click(random.choice(random_click), interval=0.7):
                click_count += 1
                continue


            if not window_control and swipe_count >= 5:
                logger.info('Swipe to the most matter failed')
                logger.info('Please check your game resolution')
                raise RequestHumanTakeover

        logger.info('Swipe to the most matter')
        # 还有一点很重要的，捐赠会有双倍的，需要领两次
        reward_number = 0
        while 1:
            self.screenshot()

            if reward_number >= 2:
                break
            if self.ui_reward_appear_click(False):
                reward_number += 1
                continue
            if self.appear_then_click(self.I_CM_PRESENT, interval=1):
                continue
        self.ui_reward_appear_click(True)
        logger.info('Donate finished')
        return True

    def _soul(self, index: int):
        """
        搞收御魂的任务
        :param index:
        :return:
        """
        match_click = {
            0: self.C_CM_1,
            1: self.C_CM_2,
            2: self.C_CM_3,
        }
        self.ui_click(match_click[index], self.I_SL_SUBMIT)
        while 1:
            self.screenshot()
            number_text = self.O_SL_NUMBER.ocr(self.device.image)
            submit_number = int(re.findall(r'\d+', number_text)[-1])
            if submit_number > 0:
                break

            if self.ocr_appear(self.O_SL_LEVEL):
                # 如果没有识别到这个，那就说明没有御魂可以提交了，要退出
                logger.warning('No soul can be submit')
                self.ui_click(self.I_UI_BACK_RED, self.I_CM_RECORDS)
                return False

            if self.click(self.L_SL_LONG, interval=2.5):
                time.sleep(1)
                continue
        # 领取奖励
        logger.info('Start to collect soul rewards')
        check_timer = Timer(3)
        check_timer.start()
        while 1:
            self.screenshot()
            if self.ui_reward_appear_click(True):
                check_timer.reset()
                continue
            if self.appear_then_click(self.I_SL_SUBMIT, interval=1):
                check_timer.reset()
                continue
            if check_timer.reached():
                break
        logger.info('Finish to collect soul rewards')
        self.wait_until_appear(self.I_CM_RECORDS)

    def _feed(self, index: int):
        logger.info('Start to feed soul')
        match_click = {
            0: self.C_CM_1,
            1: self.C_CM_2,
            2: self.C_CM_3,
        }
        self.ui_click(match_click[index], self.I_FEED_HEAP)
        logger.info('Submit to feed soul')
        click_list = random.sample([self.L_FEED_CLICK_1, self.L_FEED_CLICK_2, self.L_FEED_CLICK_3, self.L_FEED_CLICK_4], 2)
        while 1:
            self.screenshot()
            if self.appear(self.I_FEED_SUBMIT):
                break
            for click in click_list:
                self.click(click)
        logger.info('Finish to feed soul')
        # 还有一点很重要的，捐赠会有双倍的，需要领两次
        reward_number = 0
        while 1:
            self.screenshot()

            if reward_number >= 2:
                break
            if self.ui_reward_appear_click(False):
                reward_number += 1
                continue
            if self.appear_then_click(self.I_FEED_SUBMIT, interval=1):
                continue
        self.ui_reward_appear_click(True)
        logger.info('Donate finished')
        return True




if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()

