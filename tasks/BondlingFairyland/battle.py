# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta, datetime

import random

from module.server.i18n import I18n
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.BondlingFairyland.assets import BondlingFairylandAssets
from tasks.BondlingFairyland.config_battle import BattleConfig

from module.logger import logger
from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType, GeneralBattleConfig




class BondlingBattle(GeneralBattle, BondlingFairylandAssets):

    def run_battle(self, battle_config: BattleConfig, limit_count: int = None) -> bool:
        """
        :return: 如果结契成功返回True，否则返回False
        """
        logger.hr("General battle start", 2)
        self.current_count += 1
        logger.info(f'Current tasks: {I18n.trans_zh_cn(self.config.task.command)}')
        logger.info(f'Current count: {self.current_count} / {limit_count}')

        task_run_time = datetime.now() - self.start_time
        # 格式化时间，只保留整数部分的秒
        task_run_time_seconds = timedelta(seconds=int(task_run_time.total_seconds()))
        logger.info(f'Current times: {task_run_time_seconds} / {self.limit_time}')

        if self.check_load():
            # 首先要判断进入战斗的界面
            self.green_mark(battle_config.green_enable, battle_config.green_mark)

        # 进入战斗过程
        return self.catch_battle_wait(battle_config.random_click_swipt_enable)

    def check_take_over_battle(self, is_screenshot: bool, config: GeneralBattleConfig) -> bool or None:
        """
        中途接入战斗，并且接管
        :return:  赢了返回True， 输了返回False, 不是在战斗中返回None
        """
        if is_screenshot:
            self.screenshot()
        if not self.is_in_battle():
            return None

        if self.is_in_prepare(False):
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=1.5):
                    continue
                if not self.appear(self.I_BUFF):
                    break

            # 被接管的战斗，只有准备阶段才可以点绿标。
            # 因为如果是战斗中，无法保证点击的时候是否出现动画
            self.wait_until_disappear(self.I_BUFF)
            self.green_mark(config.green_enable, config.green_mark)

        # 本人选择的策略是只要进来了就算一次，不管是不是打完了
        logger.hr("Check take over battle", 2)
        self.current_count += 1
        logger.info(f'Current tasks: {I18n.trans_zh_cn(self.config.task.command)}')
        logger.info(f'Current count: {self.current_count} / {self.limit_count}')

        task_run_time = datetime.now() - self.start_time
        # 格式化时间，只保留整数部分的秒
        task_run_time_seconds = timedelta(seconds=int(task_run_time.total_seconds()))
        logger.info(f'Current times: {task_run_time_seconds} / {self.limit_time}')
        return self.battle_wait(config.random_click_swipt_enable)


    def check_load(self) -> bool:
        """
        检查战斗时候的加载动画
        如何是还在加载种，有那个要准备的按钮，就返回True
        如果已经进入战斗了，就返回False
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear(self.I_BUFF):
                return True
            if self.appear(self.I_EXIT):
                return False

    def catch_battle_wait(self, random_click_swipt_enable: bool) -> bool:
        """
        重写一个 战斗等待
        :return: 如果捕获成功返回True，否则返回False
        """
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        # 有时候 只会点击 获得奖励和开始战斗
        # 战斗过程 随机点击和滑动 防封
        logger.info("Start battle process")
        win: bool = False
        while 1:
            self.screenshot()
            # 如果捕获成功
            if self.appear_then_click(self.I_CAP_SUCCESS, action=self.C_CAP_SUCCESS,  interval=1):
                win = True
            # 如果捕获失败
            if self.appear_then_click(self.I_CAP_FAILURE, action=self.C_CAP_SUCCESS, interval=1):
                win = False

            # 如果领奖励
            if self.appear(self.I_REWARD, threshold=0.6):
                break
            if self.appear_then_click(self.I_WIN, threshold=0.6):
                continue
            if self.appear_then_click(self.I_BATTLE_SUCCESS, threshold=0.6, interval=1):
                continue
            if self.appear_then_click(self.I_BATTLE_FAIL_ABANDON, interval=1):
                continue
            if self.appear_then_click(self.I_BATTLE_FAIL, threshold=0.6, interval=1):
                continue
            # 如果开启战斗过程随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()

        # 确定获得奖励 无论是胜利还是失败
        if win:
            logger.info("Catch success")
        else:
            logger.info("Catch failure")
        while 1:
            self.screenshot()
            # 如果出现领奖励
            action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
            if self.appear_then_click(self.I_REWARD, action=action_click, interval=1.5):
                continue
            if self.appear_then_click(self.I_WIN, threshold=0.6):
                continue
            if self.appear_then_click(self.I_BATTLE_SUCCESS, threshold=0.6, interval=1):
                continue
            if self.appear_then_click(self.I_BATTLE_FAIL_ABANDON, interval=1):
                continue
            if self.appear_then_click(self.I_BATTLE_FAIL, threshold=0.6, interval=1):
                continue
            if not self.appear(self.I_REWARD):
                break
        logger.info("Get reward")
        return win
