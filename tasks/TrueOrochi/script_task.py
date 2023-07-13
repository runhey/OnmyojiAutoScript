# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from module.logger import logger
from module.exception import TaskEnd

from tasks.GameUi.game_ui import GameUi
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Orochi.script_task import ScriptTask as OrochiScriptTask
from tasks.GameUi.page import page_main, page_soul_zones


class ScriptTask(GameUi, OrochiScriptTask, GeneralBattle, GeneralInvite, GeneralRoom):

    def run(self):
        config = self.config.ture_orochi
        self.ui_get_current_page()
        self.ui_goto(page_soul_zones)
        self.orochi_enter()


    def check_true_orochi(self, screenshot=False) -> bool:
        """
        检查是否出现真蛇（要求当前的界面必须是在御魂挑战的界面）
        :return:
        """
        if screenshot:
            self.screenshot()
        return self.appear(self.I_FIND_TS)

    def run_true_orochi(self) -> bool:
        pass

