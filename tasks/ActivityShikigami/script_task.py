# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, timedelta
import time

from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.AreaBoss.assets import AreaBossAssets
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from module.logger import logger
from module.exception import TaskEnd


class ScriptTask(BaseActivity, ActivityShikigamiAssets):

    def run(self) -> None:

        config = self.config.activity_shikigami
        self.limit_time: timedelta = config.shikigami.limit_time
        self.limit_count = config.shikigami.limit_count

        self.home_main()
        self.wait_until_appear(self.I_BACK_GREEN)
        if config.general_battle.lock_team_enable:
            logger.info("Lock team")
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_UNLOCK, interval=1):
                    continue
                if self.appear(self.I_LOCK):
                    break
        else:
            logger.info("Unlock team")
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_LOCK, interval=1):
                    continue
                if self.appear(self.I_UNLOCK):
                    break




        while 1:
            if self.limit_time is not None and self.limit_time + self.start_time < datetime.now():
                logger.info("Time out")
                break
            if self.current_count >= self.limit_count:
                logger.info("Count out")
                break

            # 点击战斗
            self.wait_until_appear(self.I_FIRE)
            logger.info("Click battle")
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_FIRE, interval=1):
                    continue
                if not self.appear(self.I_FIRE):
                    break

            if self.run_general_battle(config=config.general_battle):
                logger.info("General battle success")

        self.main_home()
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd


    def home_main(self) -> bool:
        """
        从庭院到活动的爬塔界面
        :return:
        """
        logger.hr("Enter Shikigami", 2)
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_SHI, interval=1):
                continue
            if self.appear_then_click(self.I_DRUM, interval=1):
                continue
            if self.appear_then_click(self.I_BATTLE, interval=1):
                continue
            if self.appear(self.I_FIRE):
                break


    def main_home(self) -> bool:
        """
        从活动的爬塔界面到庭院
        :return:
        """
        logger.hr("Exit Shikigami", 2)
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_BACK_GREEN, interval=1):
                continue
            if self.appear(self.I_SHI):
                break

