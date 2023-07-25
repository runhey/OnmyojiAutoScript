# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_area_boss
from tasks.AreaBoss.assets import AreaBossAssets
from module.logger import logger
from module.exception import TaskEnd


class ScriptTask(GeneralBattle, GameUi, AreaBossAssets):

    def run(self) -> bool:
        """
        运行脚本
        :return:
        """
        # 直接手动关闭这个锁定阵容的设置
        self.config.area_boss.general_battle.lock_team_enable = False

        self.ui_get_current_page()
        self.ui_goto(page_area_boss)

        # # 点击探索
        # logger.info("Click explore")
        # while 1:
        #     self.screenshot()
        #     if self.appear_then_click(self.I_EXPLORE, threshold=0.6, interval=2):
        #         continue
        #     if self.appear(self.I_AREA_BOSS, threshold=0.6):
        #         break
        #
        # # 点击地狱鬼王
        # logger.info("Click area boss")
        # while 1:
        #     self.screenshot()
        #     if self.appear_then_click(self.I_AREA_BOSS, threshold=0.6, interval=2):
        #         continue
        #     if self.appear(self.I_FILTER, threshold=0.6):
        #         break

        # 点击右上角的鬼王选择
        logger.info("Click filter")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_FILTER, threshold=0.8, interval=2):
                continue
            if self.appear(self.I_BATTLE_1):
                break

        # 点击第一个鬼王
        logger.info("Click battle 1")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_BATTLE_1, threshold=0.8, interval=1):
                continue
            if self.appear(self.I_CLOSE_RED):
                break

        # 点击挑战
        logger.info("Script fire")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_FIRE, interval=1):
                continue
            if not self.appear(self.I_CLOSE_RED):  # 如果这个红色的关闭不见了才可以进行继续
                break
        logger.info("Script general battle")
        if not self.run_general_battle(self.config.area_boss.general_battle):
            logger.info("地狱鬼王第一只战斗失败")

        # 红色关闭
        logger.info("Script close red")
        self.wait_until_appear(self.I_CLOSE_RED)
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_CLOSE_RED, interval=1):
                continue
            if self.appear(self.I_FILTER):
                break
        # 只挑战一只， 退出
        if self.config.area_boss.boss.boss_number == 1:
            self.go_back()
            self.set_next_run(task="AreaBoss", success=True, finish=False)
            return True

        # 点击右上角的鬼王选择
        logger.info("Script filter")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_FILTER, threshold=0.8, interval=2):
                continue
            if self.appear(self.I_BATTLE_2):
                break

        # 点击第2个鬼王
        logger.info("Script area boss 2")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_BATTLE_2, threshold=0.8, interval=1):
                continue
            if self.appear(self.I_CLOSE_RED):
                break

        # 点击挑战
        logger.info("Script fire ")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_FIRE, interval=1):
                continue
            if not self.appear(self.I_CLOSE_RED):  # 如果这个红色的关闭不见了才可以进行继续
                break

        if not self.run_general_battle(self.config.area_boss.general_battle):
            logger.info("地狱鬼王第2只战斗失败")

        # 红色关闭
        logger.info("Script close red")
        self.wait_until_appear(self.I_CLOSE_RED)
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_CLOSE_RED, interval=1):
                continue
            if self.appear(self.I_FILTER):
                break
        # 只挑战2只， 退出
        if self.config.area_boss.boss.boss_number == 2:
            self.go_back()
            self.set_next_run(task="AreaBoss", success=True, finish=False)
            return True


        #---------------------------------------------第三只
        # 点击右上角的鬼王选择
        logger.info("Script filter")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_FILTER, threshold=0.8, interval=2):
                continue
            if self.appear(self.I_BATTLE_3):
                break
        # 点击第3个鬼王
        logger.info("Script area boss 3")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_BATTLE_3, threshold=0.8, interval=1):
                continue
            if self.appear(self.I_CLOSE_RED):
                break
        # 点击挑战
        logger.info("Script fire ")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_FIRE, interval=1):
                continue
            if not self.appear(self.I_CLOSE_RED):  # 如果这个红色的关闭不见了才可以进行继续
                break
        if not self.run_general_battle(self.config.area_boss.general_battle):
            logger.info("地狱鬼王第2只战斗失败")
        # 红色关闭
        logger.info("Script close red")
        self.wait_until_appear(self.I_CLOSE_RED)
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_CLOSE_RED, interval=1):
                continue
            if self.appear(self.I_FILTER):
                break

        # 退出
        self.go_back()
        self.set_next_run(task='AreaBoss', success=True)

        # 以抛出异常的形式结束
        raise TaskEnd

    def go_back(self) -> None:
        """
        返回, 要求这个时候是出现在  地狱鬼王的主界面
        :return:
        """
        # 点击返回
        logger.info("Script back home")
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_BACK_BLUE, threshold=0.6, interval=2):
                continue
            if self.appear(self.I_EXPLORE, threshold=0.6):
                break



