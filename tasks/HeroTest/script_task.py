# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, timedelta, time
import random  # type: ignore

from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.HeroTest.assets import HeroTestAssets
from tasks.GameUi.page import page_main
from tasks.GameUi.game_ui import GameUi

from module.logger import logger
from module.exception import TaskEnd


class ScriptTask(GameUi, BaseActivity, HeroTestAssets):

    def run(self) -> None:

        config = self.config.hero_test
        self.limit_time: timedelta = config.herotest.limit_time
        if isinstance(self.limit_time, time):
            self.limit_time = timedelta(
                hours=self.limit_time.hour,
                minutes=self.limit_time.minute,
                seconds=self.limit_time.second,
            )
        self.limit_count = config.herotest.limit_count

        self.ui_get_current_page()
        self.ui_goto(page_main)
        self.home_main()

        # # 2024-04-04 ---------------------start
        # config.herotest.ap_mode = ApMode.AP_GAME
        # # 2024-04-04 ---------------------end

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
            if (
                self.limit_time is not None
                and self.limit_time + self.start_time < datetime.now()
            ):
                logger.info("Time out")
                break
            if self.current_count >= self.limit_count:
                logger.info("Count out")
                break
            # 2
            self.wait_until_appear(self.I_BATTLE)

            # 点击战斗
            logger.info("Click battle")
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_BATTLE, interval=2):
                    self.device.stuck_record_clear()
                    continue
                if not self.appear(self.I_BATTLE):
                    break

                if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                    continue

            if self.run_general_battle(config=config.general_battle):
                logger.info("General battle success")

        self.main_home()
        self.set_next_run(task="HeroTest", success=True)
        raise TaskEnd

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        self.device.stuck_record_add("BATTLE_STATUS_S")
        self.device.click_record_clear()
        logger.info("Start battle process")
        win: bool = False
        while 1:
            self.screenshot()
            if self.appear(self.I_WIN, threshold=0.8) or self.appear(self.I_DE_WIN):
                logger.info("Battle result is win")
                if self.appear(self.I_DE_WIN):
                    self.ui_click_until_disappear(self.I_DE_WIN)
                win = True
                break

            # 如果出现失败 就点击，返回False
            if self.appear(self.I_FALSE, threshold=0.8):
                logger.info("Battle result is false")
                win = False
                break

            # 如果领奖励
            if self.appear(self.I_REWARD, threshold=0.6):
                win = True
                break

            # 如果领奖励出现金币
            if self.appear(self.I_REWARD_GOLD, threshold=0.8):
                win = True
                break
            # 如果开启战斗过程随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()

        # 再次确认战斗结果
        logger.info("Reconfirm the results of the battle")
        while 1:
            self.screenshot()
            if win:
                # 点击赢了
                action_click = random.choice([self.C_WIN_1, self.C_WIN_2, self.C_WIN_3])
                if self.appear_then_click(
                    self.I_WIN, action=action_click, interval=0.5
                ):
                    continue
                if not self.appear(self.I_WIN):
                    break
            else:
                # 如果失败且 点击失败后
                if self.appear_then_click(self.I_FALSE, threshold=0.6):
                    continue
                if not self.appear(self.I_FALSE, threshold=0.6):
                    return False
        # 最后保证能点击 获得奖励
        if not self.wait_until_appear(self.I_REWARD, wait_time=2):
            # 有些的战斗没有下面的奖励，所以直接返回
            logger.info("There is no reward, Exit battle")
            return win
        logger.info("Get reward")
        while 1:
            self.screenshot()
            # 如果出现领奖励
            action_click = random.choice(
                [self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3]
            )
            if self.appear_then_click(
                self.I_REWARD, action=action_click, interval=1.5
            ) or self.appear_then_click(
                self.I_REWARD_GOLD, action=action_click, interval=1.5
            ):
                continue
            if not self.appear(self.I_REWARD) and not self.appear(self.I_REWARD_GOLD):
                break

        return win

    def home_main(self) -> bool:
        """
        从庭院到活动的爬塔界面
        :return:
        """
        # 启动经验加成
        self.open_buff()
        self.exp_100(True)
        self.exp_50(True)
        self.close_buff()
        logger.hr("Enter HeroTest", 2)
        while 1:
            self.screenshot()
            if self.appear(self.I_BATTLE):
                logger.info("发现了战斗按钮，进入活动界面成功")
                break
            # 2024-04-04 --------------start
            if self.appear_then_click(self.I_ONE, interval=1):
                continue
            # 2024-04-04 --------------end
            if self.appear_then_click(self.I_TWO, interval=1):
                continue
            if self.appear_then_click(self.I_GBB, interval=1):
                continue

    def main_home(self) -> bool:
        """
        从活动的爬塔界面到庭院
        :return:
        """
        logger.hr("Exit HeroTest", 2)
        while 1:
            self.screenshot()
            if self.appear(self.I_ONE):
                # 关闭经验加成
                self.open_buff()
                self.exp_100(False)
                self.exp_50(False)
                self.close_buff()
                break
            if self.appear_then_click(self.I_UI_BACK_RED, interval=2):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=2):
                continue
            if self.appear_then_click(self.I_BACK, interval=2):
                continue
            if self.appear_then_click(self.I_GBB_BACK, interval=2):
                continue


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    c = Config("oas1")
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
