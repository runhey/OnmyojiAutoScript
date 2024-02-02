# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.atom.image import RuleImage

from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.game_ui import GameUi
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Pets.assets import PetsAssets
from tasks.base_task import BaseTask
from module.logger import logger

class ScriptTask(GeneralBattle, GameUi, SwitchSoul, PetsAssets, ):

    def run(self):
        # 探索测试
        self.ui_click(self.I_MAIN_GOTO_EXPLORATION, self.I_CHECK_EXPLORATION)
        self.ui_click(self.I_UI_BACK_BLUE, self.I_CHECK_MAIN)
        # 町中测试
        self.ui_click(self.I_MAIN_GOTO_TOWN, self.I_CHECK_TOWN)
        self.ui_click(self.I_TOWN_GOTO_MAIN, self.I_CHECK_MAIN)
        # 召唤测试
        self.ui_click(self.I_MAIN_GOTO_SUMMON, self.I_CHECK_SUMMON)
        self.ui_click(self.I_SUMMON_GOTO_MAIN, self.I_CHECK_MAIN)
        # 宠物屋测试
        self.ui_click(self.I_PET_HOUSE, self.I_PET_CLAW)
        self.ui_click(self.I_PET_EXIT, self.I_CHECK_MAIN)
        logger.info('Test Success')


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run()

