# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey


from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.Orochi.assets import OrochiAssets
from module.logger import logger

class ScriptTask(GeneralBattle, GameUi, OrochiAssets):

    def run(self) -> bool:
        pass

    def check_layer(self, layer: str) -> bool:
        """
        检查挑战的层数, 并选中挑战的层
        :return:
        """
        pos = self.list_find(self.L_LAYER_LIST, layer)
        if pos:
            self.device.click(x=pos[0], y=pos[1])
            return True






if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.check_layer('陆')







