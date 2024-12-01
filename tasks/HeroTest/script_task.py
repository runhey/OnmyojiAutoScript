# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, timedelta, time
import random  # type: ignore

from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.HeroTest.assets import HeroTestAssets
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_exploration
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul

from module.logger import logger
from module.exception import TaskEnd


class ScriptTask(GameUi, BaseActivity, HeroTestAssets, SwitchSoul):

    is_update = False
    is_skill = False

    def run(self) -> None:

        config = self.config.hero_test
        global is_update
        global is_skill
         # 自动换御魂
        if config.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(config.switch_soul_config.switch_group_team)
        if config.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(config.switch_soul_config.group_name, config.switch_soul_config.team_name)

        if config.herotest.layer.value == "鬼兵演武":
            is_update = True
            is_skill = False
        if config.herotest.layer.value == "兵藏秘境":
            is_skill = True
            is_update = False

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
        # 启动经验加成
        if is_update:
            self.open_buff()
            self.exp_100(True)
            self.exp_50(True)
            self.close_buff()
        self.ui_goto(page_exploration)
        self.home_main()
        # 设定是否锁定阵容
        if is_update:
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
        elif is_skill:
            if config.general_battle.lock_team_enable:
                logger.info("Lock team")
                while 1:
                    self.screenshot()
                    if self.appear_then_click(self.I_BCMJ_UNLOCK, interval=1):
                        continue
                    if self.appear(self.I_BCMJ_LOCK):
                        break
            else:
                logger.info("Unlock team")
                while 1:
                    self.screenshot()
                    if self.appear_then_click(self.I_BCMJ_LOCK, interval=1):
                        continue
                    if self.appear(self.I_BCMJ_UNLOCK):
                        break

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
            if is_update:
                self.wait_until_appear(self.I_BATTLE)
            if is_skill:
                self.wait_until_appear(self.I_BCMJ_BATTLE)

            # 如果是兵藏秘境 看看是否有兵道帖
            if is_skill:
                if not self.check_art_war_card():
                    logger.info("Art war card is not enough")
                    break
            # 点击战斗
            logger.info("Click battle")
            while 1:
                self.screenshot()
                if is_update:
                    if self.appear_then_click(self.I_BATTLE, interval=2):
                        self.device.stuck_record_clear()
                        continue
                    if not self.appear(self.I_BATTLE):
                        break
                elif is_skill:
                    if not self.check_art_war_card():
                        logger.info("Art war card is not nough")
                        break
                    if self.appear_then_click(self.I_START_CHALLENGE, interval=1):
                        continue
                    if self.appear_then_click(self.I_BCMJ_RESET_CONFIRM, interval=1):
                        continue
                    if self.appear_then_click(self.I_BCMJ_BATTLE, interval=2):
                        self.device.stuck_record_clear()
                        continue
                    if not self.appear(self.I_BCMJ_BATTLE):
                        break

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
        if not is_skill and not self.wait_until_appear(self.I_REWARD, wait_time=2):
            # 有些的战斗没有下面的奖励，所以直接返回
            logger.info("There is no reward, Exit battle")
            return win
        else:
            if self.wait_until_appear(self.I_BCMJ_SKILL_ADD_CONFIRM, wait_time=2):
                while 1:
                    self.screenshot()
                    if self.appear_then_click(self.I_BCMJ_SKILL_ADD1, interval=1):
                        break
                    if self.appear_then_click(self.I_BCMJ_SKILL_ADD2, interval=1):
                        break
                    if self.appear_then_click(self.I_BCMJ_BLESS, interval=1):
                        break
                    if self.appear_then_click(
                        self.I_BCMJ_PROPERTY_ADD_CRITICAL, interval=1
                    ):
                        break
                    if self.appear_then_click(
                        self.I_BCMJ__DEFALUT_ATTRIBUTE, interval=1
                    ):
                        break
                if self.appear_then_click(self.I_BCMJ_SKILL_ADD_CONFIRM, interval=1):
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

    def check_art_war_card(self):
        self.screenshot()
        cu = self.O_ART_WAR_CARD.ocr(image=self.device.image)
        if cu[0] >= 1:
            logger.info("Art war card is enough")
            return True
        cu = self.O_ART_WAR_CARD_PLUS.ocr(image=self.device.image)
        # 转换为int
        if cu != "":
            cu = int(cu)
        else:
            cu = 0
        if cu >= 1:
            logger.info("Art war card is not enough, but plus card is enough")
            return True
        return False

    def home_main(self) -> bool:
        """
        从庭院到活动的爬塔界面
        :return:
        """
        logger.hr("Enter HeroTest", 2)
        global is_update
        global is_skill
        while 1:
            self.screenshot()
            if is_update:
                if self.appear(self.I_BATTLE):
                    break
            if is_skill:
                if self.appear(self.I_BCMJ_BATTLE):
                    break
            if self.appear_then_click(self.I_TWO, interval=1):
                continue
            if is_update:
                if self.appear_then_click(self.I_GBB, interval=1):
                    continue
            if is_skill:
                if self.appear_then_click(self.I_BCMJ, interval=1):
                    continue

    def main_home(self) -> bool:
        """
        从活动的爬塔界面到庭院
        :return:
        """
        logger.hr("Exit HeroTest", 2)
        global is_update
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_UI_BACK_RED, interval=2):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=2):
                continue
            if self.appear_then_click(self.I_BACK, interval=2):
                continue
            if self.appear_then_click(self.I_GBB_BACK, interval=2):
                continue
            self.ui_get_current_page()
            self.ui_goto(page_main)
            if is_update:
                # 关闭经验加成
                self.open_buff()
                self.exp_100(False)
                self.exp_50(False)
                self.close_buff()
            break



if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    c = Config("oas2")
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
