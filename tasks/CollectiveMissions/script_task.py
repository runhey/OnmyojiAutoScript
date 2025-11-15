# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
from time import sleep

import random
import re
from cached_property import cached_property
from enum import Enum
from datetime import timedelta
from module.atom.image import RuleImage

from module.exception import TaskEnd, RequestHumanTakeover
from module.logger import logger
from module.base.timer import Timer
from module.atom.ocr import RuleOcr
from tasks.CollectiveMissions.config import MC

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_guild
from tasks.CollectiveMissions.assets import CollectiveMissionsAssets


class ScriptTask(GameUi, CollectiveMissionsAssets):
    """阴阳寮集体任务"""

    current_mission: MC = None

    def run(self):
        self.ui_goto_page(page_guild)
        self.ui_click(self.I_CM_SHRINE, self.I_CM_CM)
        self.ui_click(self.I_CM_CM, self.I_CM_RECORDS)
        logger.info('Start to detect missions')
        self.get_task_reward()
        if self.is_finish():
            self.exit()
            self.set_next_run(task='CollectiveMissions', success=True)
            raise TaskEnd('CollectiveMissions')
        self.select_and_update_cur_mission(self.config.collective_missions.missions_config.missions_select)
        if self.current_mission is None:
            self.exit()
            self.set_next_run(task='CollectiveMissions', success=False)
            raise TaskEnd('CollectiveMissions')
        match self.current_mission:
            case MC.FEED:
                self._feed()  # 喂 N 卡
            case MC.AW1 | MC.AW2 | MC.AW3 | MC.GR1 | MC.GR2 | MC.GR3:
                self._donate()  # 捐材料
            case MC.SO1 | MC.SO2:
                self._soul()  # 捐御魂
        self.exit()
        self.set_next_run(task='CollectiveMissions', success=True)
        raise TaskEnd('CollectiveMissions')

    def select_and_update_cur_mission(self, mission: MC) -> bool:
        """尝试选择对应任务并更新当前任务, 若选择失败(无法切换)则会停留在当前任务
        :return: 成功选择返回True
        """
        pre_mission = ''
        switch_fail_cnt, max_retry = 0, random.randint(2, 3)
        while True:
            if switch_fail_cnt >= max_retry:
                logger.warning(f'Cannot switch next mission, stop select and try run')
                return False
            self.screenshot()
            # 识别当前任务
            mission_text = self.O_CM_2.ocr(self.device.image)
            try:
                detect_mission = MC(mission_text)
                logger.info(f"Current: {detect_mission.value}, target: {mission.value}")
                self.current_mission = detect_mission
                if detect_mission == mission:
                    logger.info(f"Success select mission[{mission_text}]")
                    return True
            except ValueError as e:
                logger.warning(f'Unknown {mission_text}, skip')
            logger.info("Try switch to next mission")
            switch_fail_cnt = 0 if pre_mission != mission_text else (switch_fail_cnt + 1)
            pre_mission = mission_text
            if self.appear_then_click(self.I_CM_SWITCH, interval=0.6):
                sleep(random.uniform(0.6, 1.2))

    def _donate(self):
        """捐材料"""
        self.ui_click(self.C_CM_1, self.I_CM_PRESENT, interval=1.5)
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
        self.get_reward_and_close(self.I_CM_PRESENT)
        logger.info('Donate finished')
        return True

    def _soul(self):
        """提交御魂"""
        self.ui_click(self.C_CM_1, self.I_SL_SUBMIT)
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
        logger.info('Start to collect soul rewards')
        self.get_reward_and_close(self.I_SL_SUBMIT)
        logger.info('Finish to collect soul rewards')
        return True

    def _feed(self):
        """提交N卡"""
        logger.info('Start to feed N')
        self.ui_click(self.C_CM_1, self.I_FEED_HEAP)
        logger.info('Submit to feed N')
        click_list = random.sample([self.L_FEED_CLICK_1, self.L_FEED_CLICK_2, self.L_FEED_CLICK_3, self.L_FEED_CLICK_4], 2)
        while 1:
            self.screenshot()
            if self.appear(self.I_FEED_SUBMIT):
                break
            for click in click_list:
                self.click(click)
        logger.info('Start to collect feed N rewards')
        self.get_reward_and_close(self.I_FEED_SUBMIT)
        logger.info('Finish to collect feed N rewards')
        return True

    def exit(self):
        """退出到庭院"""
        self.ui_click(self.I_CM_CLOSE, self.I_CM_CM)
        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CM_SHRINE)
        self.ui_goto_page(page_main)

    def is_finish(self):
        """判断寮三十是否已经捐满"""
        self.screenshot()
        current, remain, total = self.O_CM_NUMBER.ocr(self.device.image)
        if current == total == 30:
            logger.info('Today\'s missions have been completed')
            return True
        return False

    def get_task_reward(self):
        """获取其他已完成的任务奖励"""
        if not self.appear(self.I_CM_GET_REWARD):
            return
        logger.info('Discover the tasks that have been completed')
        self.get_reward_and_close(self.I_CM_GET_REWARD)
        logger.info('Get task reward finished')

    def get_reward_and_close(self,  target: RuleImage):
        # 捐赠可能有双倍的，需要领两次
        reward_number = 0
        timeout_timer = Timer(3).start()
        while not timeout_timer.reached():
            self.screenshot()
            if reward_number >= 2:
                break
            if self.ui_reward_appear_click(False):
                reward_number += 1
                continue
            if self.appear_then_click(target, interval=1):
                continue
        self.ui_reward_appear_click(True)  # 兜底再尝试领取一次


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
