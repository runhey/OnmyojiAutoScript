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


class ScriptTask(GameUi, GeneralBattle, GeneralInvite, GeneralRoom):

    def run(self):
        config = self.config.ture_orochi
        self.ui_get_current_page()
        self.ui_goto(page_soul_zones)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()

