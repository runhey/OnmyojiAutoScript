# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
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
    SO4 = '御魂四'
    SO5 = '御魂五'
    FRIEND = '好友'
    UNKNOWN = '未知'

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
        elif mission == MC.AW1 or mission == MC.AW2 or mission == MC.AW3 or mission == MC.GR1 or mission == MC.GR2:
            # 其他就捐材料
            self._donate(index)
        elif mission == MC.SO4 or mission == MC.SO5:
            # 御魂就捐御魂
            # TODO
            logger.warning('Not support donate soul')

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
        if result_1 != '远远不够':
            logger.warning(f'Ocr task name: {result_1}')
            return MC.UNKNOWN
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
        elif result_2 == '御魂四':
            return MC.SO4
        elif result_2 == '御魂五':
            return MC.SO5
        return MC.UNKNOWN

    def detect_best(self) -> tuple:
        """
        自动寻找最好的任务并返回，期间记录三个任务的类型
        :return: 任务类型, 0/1/2
        """
        best_index = 0
        best_class = self.detect_one(self.O_CM_1, self.O_CM_2)
        self.missions.append(best_class)
        # 判断第二个,是否比第一个好
        last_index = self.rule.index(best_class)
        now_class = self.detect_one(self.O_CM_3, self.O_CM_4)
        self.missions.append(now_class)
        now_index = self.rule.index(now_class)
        if now_index < last_index:
            best_index = 1
            best_class = now_class
        # 判断第三个,是否比前两个好
        last_index = self.rule.index(best_class)
        now_class = self.detect_one(self.O_CM_5, self.O_CM_6)
        self.missions.append(now_class)
        if now_class == MC.FRIEND:
            logger.info('The third mission is friend')
            return best_class, best_index
        now_index = self.rule.index(now_class)
        if now_index < last_index:
            best_index = 2
            best_class = now_class
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
            self.set_next_run(task='CollectiveMissions', success=True, finish=True, target=self.start_time+ timedelta(hours=2))
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
        swipe_count = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_CM_MATTER):
                break
            if self.swipe(match_swipe[max_index], interval=2.5):
                swipe_count += 1
                time.sleep(1.5)
                continue
            # if self.appear_then_click(match_image[max_index], interval=1):
            #     self.device.click_record_clear()
            #     continue

            # 为什么使用window_message无法滑动
            if swipe_count >= 5:
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







if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()

