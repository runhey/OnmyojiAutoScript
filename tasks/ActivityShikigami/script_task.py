# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import random
from datetime import datetime, timedelta, time

from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.AreaBoss.assets import AreaBossAssets
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.BaseActivity.config_activity import ApMode
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.GameUi.page import page_main
from tasks.GameUi.game_ui import GameUi

from module.logger import logger
from module.exception import TaskEnd


class ScriptTask(GameUi, BaseActivity, ActivityShikigamiAssets):

    def run(self) -> None:

        config = self.config.activity_shikigami
        self.limit_time: timedelta = config.general_climb.limit_time
        if isinstance(self.limit_time, time):
            self.limit_time = timedelta(hours=self.limit_time.hour, minutes=self.limit_time.minute,
                                        seconds=self.limit_time.second)
        self.limit_count = config.general_climb.limit_count

        self.ui_get_current_page()
        self.ui_goto(page_main)
        self.home_main()

        # # 2024-04-04 ---------------------start
        # config.general_climb.ap_mode = ApMode.AP_GAME
        # # 2024-04-04 ---------------------end
        # 选择是游戏的体力还是活动的体力
        current_ap = config.general_climb.ap_mode
        self.switch(current_ap)

        # 设定是否锁定阵容
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

        # 流程应该是 在页面处：
        # 1. 判定计数是否超了，时间是否超了
        # 2. 如果是消耗活动体力，判定活动体力是否足够 如果是消耗一般的体力，判定一般体力是否足够
        # 3. 如果开启买体力，就买体力
        # 4. 如果开启了切换到游戏体力，就切换
        while 1:
            # 1
            if self.limit_time is not None and self.limit_time + self.start_time < datetime.now():
                logger.info("Time out")
                break
            if self.current_count >= self.limit_count:
                logger.info("Count out")
                break
            # 2
            self.wait_until_appear(self.I_FIRE)
            is_remain = self.check_ap_remain(current_ap)
            # 如果没有剩余了且这个时候是体力，就退出活动
            if not is_remain and current_ap == ApMode.AP_GAME:
                logger.info("Game ap out")
                break
            # 如果不是那就切换到体力
            elif not is_remain and current_ap == ApMode.AP_ACTIVITY:
                if config.general_climb.activity_toggle:
                    logger.info("Activity ap out and switch to game ap")
                    current_ap = ApMode.AP_GAME
                    self.switch(current_ap)
                else:
                    logger.info("Activity ap out")
                    break

            # 点击战斗
            logger.info("Click battle")
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_FIRE, interval=2):
                    continue
                if not self.appear(self.I_FIRE):
                    break
                if self.appear_then_click(self.I_C_CONFIRM1, interval=0.6):
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                    continue

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
            if self.appear(self.I_FIRE):
                break
            # 2024-04-04 --------------start
            if self.appear_then_click(self.I_N_BATTLE, interval=1):
                continue
            # 2024-04-04 --------------end
            if self.appear_then_click(self.I_SHI, interval=1):
                continue
            if self.appear_then_click(self.I_DRUM, interval=1):
                continue
            if self.appear_then_click(self.I_BATTLE, interval=1):
                continue

    def main_home(self) -> bool:
        """
        从活动的爬塔界面到庭院
        :return:
        """
        logger.hr("Exit Shikigami", 2)
        while 1:
            self.screenshot()
            if self.appear(self.I_SHI):
                break
            if self.appear_then_click(self.I_UI_BACK_RED, interval=2):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=2):
                continue
            if self.appear_then_click(self.I_BACK_GREEN, interval=2):
                continue

    def check_ap_remain(self, current_ap: ApMode) -> bool:
        """
        检查体力是否足够
        :return: 如何还有体力，返回True，否则返回False
        """
        self.screenshot()
        if current_ap == ApMode.AP_ACTIVITY:
            cu, res, total = self.O_REMAIN_AP_ACTIVITY.ocr(image=self.device.image)
            if cu == 0 and cu + res == total:
                logger.warning("Activity ap not enough")
                return False
            return True

        elif current_ap == ApMode.AP_GAME:
            cu, res, total = self.O_REMAIN_AP.ocr(image=self.device.image)
            if cu == total and cu + res == total:
                if cu > total:
                    logger.warning(f'Game ap {cu} more than total {total}')
                    return True
                logger.warning(f'Game ap not enough: {cu}')
                return False

            return True

    def switch(self, current_ap: ApMode) -> None:
        """
        切换体力
        :param current_ap:
        :return:
        """
        if current_ap == ApMode.AP_ACTIVITY:
            logger.info("Select activity ap")
            while 1:
                self.screenshot()
                if self.appear(self.I_AP_ACTIVITY):
                    break
                if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                    continue
                if self.appear(self.I_AP, interval=1):
                    self.appear_then_click(self.I_SWITCH, interval=2)  # 点击切换
        else:
            logger.info("Select game ap")
            while 1:
                self.screenshot()
                if self.appear(self.I_AP):
                    break
                if self.appear(self.I_AP_ACTIVITY, interval=1):
                    self.appear_then_click(self.I_SWITCH, interval=2)

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 重写
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info("Start battle process")
        self.C_RANDOM_LEFT.name = "BATTLE_RANDOM"
        self.C_RANDOM_RIGHT.name = "BATTLE_RANDOM"
        self.C_RANDOM_TOP.name = "BATTLE_RANDOM"
        self.C_RANDOM_BOTTOM.name = "BATTLE_RANDOM"
        while 1:
            self.screenshot()
            # 如果出现了 “获得奖励”
            reward_click = random.choice([self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM])
            if self.appear_then_click(self.I_UI_REWARD, action=reward_click, interval=1.3):
                continue
            # 如果出现了 “鼓”
            if self.appear(self.I_WIN):
                logger.info("Win")
                while 1:
                    self.screenshot()
                    if not self.appear(self.I_WIN):
                        break
                    if self.appear_then_click(self.I_WIN, action=self.C_RANDOM_ALL, interval=1.1):
                        continue
                return True
            # 失败 -> 正常人不会失败
            if self.appear(self.I_FALSE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False
            # 如果开启战斗过程随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
