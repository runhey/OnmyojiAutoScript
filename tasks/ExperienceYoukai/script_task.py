# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from cached_property import cached_property

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_team, page_shikigami_records
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.ExperienceYoukai.assets import ExperienceYoukaiAssets

class ScriptTask(GameUi, GeneralBattle, GeneralRoom, GeneralInvite, SwitchSoul, ExperienceYoukaiAssets):

    def run(self):
        con = self.config.experience_youkai
        self.ui_get_current_page()
        self.ui_goto(page_team)
        self.check_zones('经验妖怪')

        self.exp_exit()

    def exp_exit(self, con=None):
        self.ui_get_current_page()
        self.ui_goto(page_main)
        # if con.buff_gold_50_click or con.buff_gold_100_click:
        #     self.open_buff()
        #     if con.buff_gold_50_click:
        #         self.gold_50(False)
        #     if con.buff_gold_100_click:
        #         self.gold_100(False)
        #     self.close_buff()

        self.set_next_run(task='ExperienceYoukai', success=True, finish=False)
        raise TaskEnd('ExperienceYoukai')

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
