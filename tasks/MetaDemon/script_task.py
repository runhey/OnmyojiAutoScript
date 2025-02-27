# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from cached_property import cached_property
from datetime import datetime
from time import sleep

from tasks.Component.config_base import ConfigBase, TimeDelta, DateTime, Time
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.MetaDemon.config import MetaDemon
from tasks.MetaDemon.assets import MetaDemonAssets

from module.logger import logger
from module.exception import TaskEnd
from tasks.Restart.assets import RestartAssets
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from module.base.timer import Timer

"""超鬼王"""


class ScriptTask(GeneralBattle, SwitchSoul, GameUi, MetaDemonAssets):

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
        self.ui_get_current_page()
        self.ui_goto(page_main)

        boss_timer = Timer(200)
        boss_timer.start()
        while 1:
            self.screenshot()
            sleep(0.1)
            if boss_timer.reached():
                self.config.notifier.push(title='超鬼王', message='识别超时退出')
                break
            if self.appear(self.I_BACK_CHECK):
                self.click(self.I_RED_BACK, interval=1.5)
                break
            if self.appear_then_click(RestartAssets.I_HARVEST_CHAT_CLOSE):
                boss_timer.reset()
                continue
            if self.appear_then_click(ActivityShikigamiAssets.I_SHI, interval=1):
                boss_timer.reset()
                continue
            if self.appear_then_click(self.I_A2):
                boss_timer.reset()
                continue
            if self.appear_then_click(self.I_A3, interval=1):
                boss_timer.reset()
                continue
            if self.appear_then_click(self.I_A4, interval=1):
                boss_timer.reset()
                continue
            if self.appear_then_click(self.I_A5, interval=1):
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')
                boss_timer.reset()
                continue
            if self.appear_then_click(self.I_A6, interval=1):
                boss_timer.reset()
                continue

        config: MetaDemon = self.config.model.meta_demon
        # 主循环
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_MAIN):
                logger.info('Exit MetaDemon')
                break
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1):
                continue
        self.set_next_run(task="MetaDemon", success=True)
        raise TaskEnd

    @cached_property
    def battle_config(self):
        config = GeneralBattleConfig()
        config.lock_team_enable = False
        return config

    def ensure_ticket(self, screenshot: bool = False) -> bool:
        if screenshot:
            self.screenshot()
        cu, res, total = self.O_MD_TICKET.ocr(self.device.image)
        if cu <= 0:
            return False
        return True

    def check_exhaustion(self, screenshot: bool = False) -> bool:
        # EXHAUSTION
        if screenshot:
            self.screenshot()
        cu, res, total = self.O_MD_EXHAUSTION.ocr(self.device.image)
        if cu >= 100:
            return False
        return True

    def current_exhaustion(self) -> int:
        self.screenshot()
        cu, res, total = self.O_MD_EXHAUSTION.ocr(self.device.image)
        return int(cu)

    def click_fire(self):
        while 1:
            self.screenshot()
            if not self.appear(self.I_MD_FIRE):
                self.screenshot()
                if not self.appear(self.I_MD_FIRE):
                    break
            if self.appear_then_click(self.I_MD_FIRE, interval=2):
                continue

    def buy_tea(self):
        pass

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
