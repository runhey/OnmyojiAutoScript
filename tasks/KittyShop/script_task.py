# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from cached_property import cached_property

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer
from module.atom.image import RuleImage

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.KittyShop.assets import KittyShopAssets

class SelectFailed(Exception):
    pass

class ScriptTask(GameUi, ActivityShikigamiAssets, KittyShopAssets):

    MAIN_BUSY: list = [KittyShopAssets.I_MAIN_BUSY_1,
                       KittyShopAssets.I_MAIN_BUSY_2,
                       KittyShopAssets.I_MAIN_BUSY_3,
                       KittyShopAssets.I_MAIN_BUSY_4,
                       KittyShopAssets.I_MAIN_BUSY_5]

    def run(self) -> None:
        self.ui_get_current_page()
        self.ui_goto(page_main)
        while 1:
            self.screenshot()
            if self.appear(self.I_START_FARMING):
                break
            if self.appear_then_click(self.I_GO1, interval=2):
                continue
            if self.appear_then_click(self.I_SHI, interval=2):
                continue
        logger.hr('Start Kitty Shop')
        attempts = int(self.config.model.kitty_shop.kitty_shop_config.kitty_attempts)
        for _ in range(max(attempts, 0)):
            self._run()

        self.ui_click(self.I_UI_BACK_YELLOW, stop=self.I_CHECK_MAIN, interval=2.4)
        self.set_next_run(task="KittyShop", success=True)
        raise TaskEnd

    def _run(self):
        logger.hr('Kitty Shop', level=1)
        for trial in range(3):
            try:
                self._select_kitty()
                break
            except SelectFailed:
                self.ui_click(self.I_UI_BACK_YELLOW, stop=self.I_START_FARMING, interval=2.2)
                logger.error('Select kitty failed')

        self.ui_click(self.I_START_ENSURE, stop=self.I_MAIN_FLAG)
        logger.info('Start farming')
        while 1:
            # 哪里亮了点哪里
            self.screenshot()
            if self.appear(self.I_MAIN_SHARE):
                break
            if self.config.model.kitty_shop.kitty_shop_config.kitty_quit_when_finished:
                if self.appear_then_click(self.I_UI_CONFIRM, interval=0.7):
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=0.7):
                    continue
                if self.appear_then_click(self.I_MAIN_FINSH, interval=1):
                    continue

            if not self.appear(self.I_MAIN_FLAG):
                continue
            if self.appear_then_click(self.I_MAIN_GIFT, interval=0.7):
                continue
            if self.appear_then_click(self.I_MAIN_ADD, interval=0.6):
                continue
            if self.appear(self.I_MAIN_FLAG1):
                self._main_select_kitty()
                continue

        logger.info('Farming done')
        while 1:
            self.screenshot()
            if self.appear(self.I_START_FARMING):
                break
            self.click(self.I_MAIN_FLAG1, interval=2)

    def _select_kitty(self):
        self.ui_click(self.I_START_FARMING, stop=self.I_START_ENSURE)

        index_timer = Timer(1.2).start()
        index_cnt = 0
        while 1:
            self.screenshot()
            if index_timer.reached():
                index_cnt += 1
                index_timer.reset()

            if not self.appear(self.I_UNSELECTED):
                break
            match index_cnt:
                case 0:
                    self.click(self.C_SELECT_1, interval=1.2)
                case 1:
                    self.click(self.C_SELECT_2, interval=1.2)
                case 2:
                    self.click(self.C_SELECT_3, interval=1.2)
                case 3 | 7 | 11:
                    self.click(self.C_SELECT_4, interval=1.2)
                case 5 | 10:
                    self.swipe(self.S_SELECTION, interval=1.5)
                case 12:
                    raise SelectFailed('Select failed')
        logger.info('Select all kitties done')

    def _main_select_kitty(self):
        for busy in self.MAIN_BUSY:
            if self.appear(busy):
                continue
            self.click(busy, interval=1.3)
            break






if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run()
