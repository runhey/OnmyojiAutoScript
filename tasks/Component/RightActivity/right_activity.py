# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from module.atom.image import RuleImage
from module.logger import logger

from tasks.base_task import BaseTask
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from tasks.Component.RightActivity.assets import RightActivityAssets


class RightActivity(GameUi, RightActivityAssets):
    def enter(self, target: RuleImage):
        self.ui_get_current_page()
        self.ui_goto(page_main)
        self.ui_click_until_disappear(target, interval=3.5)

    def right_open(self):
        self.ui_click(self.I_RA_CLOSE, self.I_RA_OPEN, interval=2)

    def right_close(self):
        self.ui_click(self.I_RA_OPEN, self.I_RA_CLOSE, interval=2)


