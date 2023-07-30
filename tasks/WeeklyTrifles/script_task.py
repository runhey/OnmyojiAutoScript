# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_team

class ScriptTask(GameUi):

    def run(self):

        self.set_next_run(task='WeeklyTrifles', success=True, finish=True)
        raise TaskEnd('WeeklyTrifles')