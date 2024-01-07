# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import time, datetime, timedelta

from module.exception import TaskEnd
from module.logger import logger

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_soul_zones
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.EternitySea.assets import EternitySeaAssets
from tasks.Orochi.config import UserStatus

class ScriptTask(GameUi, GeneralBattle, GeneralRoom, GeneralInvite, SwitchSoul, EternitySeaAssets):

    def run(self):
        config = self.config.model.eternity_sea
        
        self.ui_get_current_page()
        self.ui_goto(page_soul_zones)

        match config.eternity_sea_config.user_status:
            case UserStatus.ALONE:
                success = self.run_alone()
            case _:
                logger.error('Unknown user status')

        if success:
            self.set_next_run('EternitySea', finish=True, success=True)
        else:
            self.set_next_run('EternitySea', finish=False, success=False)

        raise TaskEnd('EternitySea')

    def run_alone(self):
        config = self.config.model.eternity_sea

        logger.info('Start run alone')
        self.ui_get_current_page()
        self.ui_goto(page_soul_zones)

        self.enter_eternity_sea()

        def is_in_eternity_sea(screenshot=False) -> bool:
            if screenshot:
                self.screenshot()
            return self.appear(self.I_ETERNITY_SEA_FIRE)
        
        limit_time = config.eternity_sea_config.limit_time
        limit_datetime: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute, seconds=limit_time.second)

        while 1:
            self.screenshot()

            if not is_in_eternity_sea():
                continue

            if self.current_count >= config.eternity_sea_config.limit_count:
                logger.info('EternitySea count limit out')
                break
            if datetime.now() - self.start_time >= limit_datetime:
                logger.info('EternitySea time limit out')
                break

            # 点击挑战
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_ETERNITY_SEA_FIRE, interval=1):
                    pass

                if not self.appear(self.I_ETERNITY_SEA_FIRE):
                    self.run_general_battle(config=config.general_battle_config)
                    break

    def enter_eternity_sea(self):
        logger.info('Enter eternity_sea')
        while True:
            self.screenshot()
            if self.appear(self.I_FORM_TEAM):
                return True
            if self.appear_then_click(self.I_ETERNITY_SEA, interval=1):
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
