# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from tasks.base_task import BaseTask
from tasks.GeneralBattle.general_battle import GeneralBattle
from tasks.AreaBoss.assets import AreaBossAssets
from module.logger import logger


class ScriptTask(GeneralBattle, AreaBossAssets):

    def run(self) -> bool:
        """
        运行脚本
        :return:
        """
        # 直接手动关闭这个锁定阵容的设置
        self.config.area_boss.general_battle.lock_team_enable = False

        # # 点击探索
        # while 1:
        #     self.screenshot()
        #     if self.appear_then_click(self.I_EXPLORE, threshold=0.6, interval=2):
        #         continue
        #     if self.appear(self.I_AREA_BOSS, threshold=0.6):
        #         break
        #
        # # 点击地狱鬼王
        # while 1:
        #     self.screenshot()
        #     if self.appear_then_click(self.I_AREA_BOSS, threshold=0.6, interval=2):
        #         continue
        #     if self.appear(self.I_FILTER, threshold=0.6):
        #         break
        #
        # # 点击右上角的鬼王选择
        # while 1:
        #     self.screenshot()
        #     if self.appear_then_click(self.I_FILTER, threshold=0.8, interval=2):
        #         continue
        #     if self.appear(self.I_BATTLE_1):
        #         break
        #
        # # 点击第一个鬼王
        # while 1:
        #     self.screenshot()
        #     if self.appear_then_click(self.I_BATTLE_1, threshold=0.8, interval=1):
        #         continue
        #     if self.appear(self.I_CLOSE_RED):
        #         break

        # 点击挑战
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_FIRE, interval=1):
                continue
            if not self.appear(self.I_CLOSE_RED):  # 如果这个红色的关闭不见了才可以进行继续
                break

        if not self.run_general_battle(self.config.area_boss.general_battle):
            print('打不过')
        return True
