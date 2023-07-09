# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from module.exception import TaskEnd


class ScriptTask(GameUi):

    def run(self) -> None:
        self.ui_get_current_page()
        self.ui_goto(page_main)
        raise TaskEnd('Goto main end')
