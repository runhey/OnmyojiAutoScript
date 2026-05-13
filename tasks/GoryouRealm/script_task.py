# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, timedelta
from module.exception import TaskEnd
from module.logger import logger
from random import choice
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_shikigami_records, page_goryou_realm
from tasks.GoryouRealm.assets import GoryouRealmAssets
from tasks.GoryouRealm.config import GoryouClass


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, GoryouRealmAssets):

    def run(self):
        con = self.config.goryou_realm
        limit_time = con.goryou_config.limit_time
        self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute,
                                               seconds=limit_time.second)
        if con.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(con.switch_soul_config.switch_group_team)
        self.ui_get_current_page()
        self.ui_goto(page_goryou_realm)

        match_click = {
            GoryouClass.Dark_Divine_Dragon: self.C_GR_C_1,
            GoryouClass.Dark_Hakuzousu: self.C_GR_C_2,
            GoryouClass.Dark_Black_Panther: self.C_GR_C_3,
            GoryouClass.Dark_Peacock: self.C_GR_C_4,
        }
        goryou_class = con.goryou_config.goryou_class
        if goryou_class == GoryouClass.RANDOM:
            goryou_class = choice(list(match_click.keys()))
        while 1:
            self.screenshot()
            if self.appear(self.I_GR_FIRE):
                logger.info('Enter GoryouRealm')
                break
            if self.click(match_click[goryou_class], interval=1):
                continue
        self.check_lock(con.general_battle_config.lock_team_enable, self.I_GR_LOCK, self.I_GR_UNLOCK)

        # 开始循环
        while 1:
            self.screenshot()
            if not self.appear(self.I_GR_FIRE):
                continue

            if self.current_count >= con.goryou_config.limit_count:
                logger.info('GoryouRealm count limit out')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('GoryouRealm time limit out')
                break
            ticket = self.O_GR_TICKET.ocr(self.device.image)
            if ticket == 0:
                break

            # 点击挑战
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_GR_FIRE, interval=1):
                    pass
                if not self.appear(self.I_GR_FIRE):
                    self.run_general_battle(config=con.general_battle_config)
                    break


        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_EXPLORATION)
        logger.info('Back to exploration')
        self.set_next_run(task='GoryouRealm', success=True, finish=True)
        raise TaskEnd




if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
