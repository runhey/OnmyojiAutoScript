# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from cached_property import cached_property
from datetime import datetime
from time import sleep


from module.base.timer import Timer
from module.logger import logger
from module.exception import TaskEnd


from tasks.Component.RightActivity.right_activity import RightActivity
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.MetaDemon.config import MetaDemon
from tasks.MetaDemon.assets import MetaDemonAssets
from tasks.Restart.assets import RestartAssets
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets


class ScriptTask(RightActivity, GeneralBattle, SwitchSoul, GameUi, MetaDemonAssets):

    def run(self):
        if self.config.meta_demon.switch_soul.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(self.config.meta_demon.switch_soul.switch_group_team)

        if self.config.meta_demon.switch_soul.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(self.config.meta_demon.switch_soul.group_name,
                                         self.config.meta_demon.switch_soul.team_name)

        self.enter(self.I_RIGHT_ENTER)
        while 1:
            self.screenshot()
            if self.appear(self.I_FIND_DEMON) or self.appear(self.I_BATTLE_DEMON):
                break
            if self.appear_then_click(self.I_ENTER2, interval=1):
                continue
        if self.config.meta_demon.meta_demon_config.meta_crafting_card:
            self.crafting()

        boss_timer = Timer(120)
        boss_timer.start()
        while 1:
            battle_processing = False
            self.screenshot()
            if not (self.appear(self.I_FIND_DEMON) or self.appear(self.I_BATTLE_DEMON)):
                continue

            # 先看自己有没有鬼王要打
            if not self.appear(self.I_BOSS_EMPTY):
                self.click(self.I_BOSS_EMPTY, interval=1.5)
                battle_processing = True
            # 看别人的是否给我共享鬼王
            if not battle_processing:
                if not self.appear(self.I_BOSS_EMPTY_1):
                    self.click(self.I_BOSS_EMPTY_1, interval=1.5)
                    battle_processing = True
                elif not self.appear(self.I_BOSS_EMPTY_2):
                    self.click(self.I_BOSS_EMPTY_2, interval=1.5)
                    battle_processing = True
            # 是否喝茶 疲劳满了就不打了
            current_exhaustion = self.current_exhaustion()
            if current_exhaustion > 99:
                if self.config.meta_demon.meta_demon_config.auto_tea:
                    logger.info('Exhaustion is full, buy tea')
                    boss_timer.reset()
                    self.buy_tea()
                else:
                    logger.info('Exhaustion is full, exit')
                    break
            # 正式战斗
            if battle_processing and self.appear(self.I_BATTLE_DEMON):
                boss_timer.reset()
                self.battle_boss()
                continue

            # 自己召唤鬼王
            if self.find_demon():
                boss_timer.reset()
                continue

        # 退出
        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_MAIN, interval=1.4)
        logger.info('Exit MetaDemon')
        self.set_next_run(task="MetaDemon", success=True)
        raise TaskEnd

    def current_exhaustion(self) -> int:
        self.screenshot()
        cu, res, total = self.O_MD_EXHAUSTION.ocr(self.device.image)
        return int(cu)

    def buy_tea(self):
        pass

    def crafting(self):
        """
        把一星合成二星
        @return:
        """
        logger.info('Star crafting 1 star to 2 star')
        self.ui_click(self.I_CRAFTING_1, self.I_CRAFTING_START, interval=1.5)
        timer = Timer(3).start()
        count = 0
        while 1:
            self.screenshot()
            if self.ui_reward_appear_click():
                timer.reset()
                continue
            if timer.reached() or count > 3:
                break
            if not self.ocr_appear(self.O_CRAFTING_CARD_1):
                break
            if self.appear(self.I_CRAFTING_EMPTY) or self.appear(self.I_CRAFTING_EMPTY_NEW):
                if self.appear_then_click(self.I_CRAFTING_CARD_STAR_1, interval=1):
                    timer.reset()
                continue
            else:
                self.appear_then_click(self.I_CRAFTING_START, interval=3)
                count += 1
                timer.reset()
                continue
        logger.info('Finish star crafting')
        self.ui_click_until_disappear(self.I_UI_BACK_RED, interval=1)

    def find_demon(self) -> bool:
        """
        召唤鬼王
        @return:
        """
        logger.info('Find demon')
        while 1:
            self.screenshot()
            if self.appear(self.I_BATTLE_DEMON) and not self.appear(self.I_BOSS_EMPTY):
                break
            if self.appear_then_click(self.I_FIND_DEMON, interval=3.5):
                continue
        self.screenshot()
        return True

    def battle_boss(self) -> bool:
        logger.info('Battle boss')
        self.ui_click_until_disappear(self.I_BATTLE_DEMON, interval=1.8)
        battle_config = GeneralBattleConfig()
        battle_config.lock_team_enable = False
        if self.run_general_battle(battle_config):
            return True
        return False

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 重写
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info("Start battle process")
        while 1:
            self.screenshot()
            # if self.appear_then_click(self.I_WIN, interval=1):
            #     continue
            if self.appear(self.I_WIN):
                logger.info('Win battle')
                self.ui_click_until_disappear(self.I_WIN)
                return True

            if self.appear(self.I_MD_BATTLE_FAILURE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_MD_BATTLE_FAILURE)
                return False


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
    # t.screenshot()
    # print(t.current_exhaustion())
