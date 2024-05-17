# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from tasks.Dance.assets import DanceAssets
from tasks.GameUi.game_ui import GameUi
from tasks.Component.Summon.summon import Summon
from module.exception import TaskEnd
from module.device.device import Device
from module.logger import logger

class ScriptTask(GameUi, Summon, DanceAssets,Device):

    def run(self):
        logger.warning(f'Ensured user is on the dance start interface and requires manual invitation to dance followed by track selection.')
        while 1:
            self.screenshot()
            self.click_record_clear()
            if self.appear(self.I_TAP_TO_DANCE):
                self.appear_then_click(self.I_TAP_TO_DANCE)
                continue
            if self.appear(self.I_TAP_TO_RANDOM_DANCE):
                self.appear_then_click(self.I_TAP_TO_DANCE)
                continue
            if self.appear(self.I_DANCE_END):
                logger.warning(f'Dance Task End')
                break
        raise TaskEnd('DanceTril')


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
