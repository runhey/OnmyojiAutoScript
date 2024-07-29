# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from cached_property import cached_property



from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_soul_zones, page_shikigami_records
from module.logger import logger
from module.exception import TaskEnd


from time import sleep
from datetime import time, datetime, timedelta

from tasks.Sougenbi.assets import SougenbiAssets
from tasks.Sougenbi.config import SougenbiConfig, SougenbiClass

from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_six_gates
from module.logger import logger


class ScriptTask(GameUi, SwitchSoul):

    @property
    def _config(self):
        return self.config.model.six_realms

    def run(self):
        if self._config.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(self._config.switch_soul_config.switch_group_team)
        if self._config.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(
                self._config.switch_soul_config.group_name,
                self._config.switch_soul_config.team_name
            )
        self.ui_get_current_page()
        self.ui_goto(page_six_gates)

        self.set_next_run('SixRealms', success=True, finish=True)
        raise TaskEnd

    def run_moon_sea(self):
        pass






if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
