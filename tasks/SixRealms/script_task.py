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
from tasks.SixRealms.moon_sea.moon_sea import MoonSea
from module.logger import logger


class ScriptTask(GameUi, SwitchSoul, MoonSea):

    @property
    def _config(self):
        return self.config.model.six_realms

    def run(self):
        if self._config.switch_soul_config_1.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(self._config.switch_soul_config_1.switch_group_team)
        if self._config.switch_soul_config_1.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(
                self._config.switch_soul_config_1.group_name,
                self._config.switch_soul_config_1.team_name
            )
        if self._config.switch_soul_config_2.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(self._config.switch_soul_config_2.switch_group_team)
        if self._config.switch_soul_config_2.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(
                self._config.switch_soul_config_2.group_name,
                self._config.switch_soul_config_2.team_name
            )
        self.ui_get_current_page()
        self.ui_goto(page_six_gates)

        self.run_moon_sea()

        # 退出六道
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_EXPLORATION) or self.appear(self.I_CHECK_MAIN):
                break
            if self.appear_then_click(self.I_BACK_EXIT, interval=2):
                continue

        self.set_next_run('SixRealms', success=True, finish=True)
        raise TaskEnd

    def run_moon_sea(self):
        self._run_moon_sea()
        self.ui_click(self.I_BACK_EXIT, self.I_CHECK_SIX_GATES)






if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
