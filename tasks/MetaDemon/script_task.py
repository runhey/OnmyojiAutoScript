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
from tasks.GameUi.page import page_main
from tasks.MetaDemon.config import MetaDemon
from tasks.MetaDemon.assets import MetaDemonAssets

from module.logger import logger
from module.exception import TaskEnd

class ScriptTask(GeneralBattle, SwitchSoul, GameUi, MetaDemonAssets):

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_main)
        while 1:
            self.screenshot()
            if self.appear(self.I_MD_FIND):
                break
            if self.appear(self.I_MD_FIRE):
                break
            if self.appear_then_click(self.I_MD_ENTER, interval=1.5):
                continue
            if self.appear_then_click(self.I_MD_MAIN, interval=1.5):
                continue

        config: MetaDemon = self.config.model.meta_demon
        # 主循环
        while 1:
            self.screenshot()
            if not self.appear(self.I_MD_GIFT_BOX):
                continue
            # 检查是否有票
            if not self.ensure_ticket():
                logger.info('There is no common ticket')
                self.set_next_run('MetaDemon', finish=True,
                                  target=config.scheduler.interval + datetime.now().replace(second=0, microsecond=0))
                break
            # 检查疲劳°
            if not self.check_exhaustion():
                logger.info('Exhaustion is more than 100')
                if config.meta_demon_config.auto_tea:
                    logger.info('Try to buy tea')
                    self.buy_tea()
                    continue
                else:
                    logger.info('Stop because of exhaustion is more than 100')
                    interval_delta = TimeDelta(minutes=self.current_exhaustion())
                    self.set_next_run('MetaDemon', finish=True,
                                      target=interval_delta + datetime.now().replace(second=0, microsecond=0))
                    break
            # 寻找鬼王
            if self.appear_then_click(self.I_MD_FIND, interval=1.5):
                continue
            #
            if self.appear(self.I_MD_FIRE) and self.appear(self.I_MD_FIRE_COMMON):
                if self.ocr_appear(self.O_MD_COUNT_INFO):
                    # 结算中
                    logger.info('Waiting for settlement')
                    sleep(1)
                    continue
                # 是否为极
                if self.appear(self.I_MD_EXTREME):
                    logger.info('Find extreme Demon')
                    if config.meta_demon_config.extreme_notify:
                        self.config.notifier.push(title='超鬼王', content=f"发现极鬼王")
                        self.set_next_run('MetaDemon', finish=True,
                                          target=config.scheduler.interval + datetime.now().replace(second=0, microsecond=0))
                        break
                    else:
                        pass
                while 1:
                    self.screenshot()
                    if self.appear(self.I_MD_FIRE) and self.appear(self.I_MD_FIRE_COMMON):
                        pass
                    else:
                        break
                    if self.appear_then_click(self.I_MD_FIRE, interval=2):
                        continue
                self.run_general_battle(config=self.battle_config)
        # exit
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_MAIN):
                logger.info('Exit MetaDemon')
                break
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1):
                continue
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

