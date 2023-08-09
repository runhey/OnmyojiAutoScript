# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from tasks.Sougenbi.assets import SougenbiAssets
from tasks.Sougenbi.config import SougenbiConfig, SougenbiClass
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_soul_zones, page_shikigami_records
from module.logger import logger
from module.exception import TaskEnd

class ScriptTask(GeneralBattle, GameUi, SwitchSoul, SougenbiAssets):

    def run(self):
        con = self.config.sougenbi
        s_con: SougenbiConfig = con.sougenbi_config
        limit_time = con.sougenbi_config.limit_time
        self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute,
                                               seconds=limit_time.second)
        if s_con.buff_enable:
            self.ui_get_current_page()
            self.ui_goto(page_main)
            self.open_buff()
            if s_con.buff_gold_50_click:
                self.gold_50(True)
            if s_con.buff_gold_100_click:
                self.gold_100(True)
            if s_con.buff_exp_50_click:
                self.exp_50(True)
            if s_con.buff_exp_100_click:
                self.exp_100(True)
            self.close_buff()

        if con.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(con.switch_soul_config.switch_group_team)
        if con.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(con.switch_soul_config.group_name, con.switch_soul_config.team_name)

        self.ui_get_current_page()
        self.ui_goto(page_soul_zones)
        while 1:
            self.screenshot()
            if self.appear(self.I_S_CHECK_SOUGENBI):
                break
            if self.appear_then_click(self.I_S_SOUGENBI, interval=1):
                continue
        logger.info('Click sougenbi in soul zones')
        sleep(0.5)
        image_target = None
        click_target = None
        number_target = None
        match con.sougenbi_config.sougenbi_class:
            case SougenbiClass.GREED:
                image_target = self.I_S_FIRE_GREED
                click_target = self.C_C_GREED
                number_target = self.O_S_GREED
            case SougenbiClass.Anger:
                image_target = self.I_S_FIRE_ANGER
                click_target = self.C_C_ANGER
                number_target = self.O_S_ANGER
            case SougenbiClass.Foolery:
                image_target = self.I_S_FIRE_FOOLERY
                click_target = self.C_C_FOOLERY
                number_target = self.O_S_FOOLERY
            case _:
                raise ValueError('Sougenbi class error')
        self.check_lock(con.general_battle_config.lock_team_enable, self.I_S_TEAM_LOCK, self.I_S_TEAM_UNLOCK)
        while 1:
            self.screenshot()
            if self.appear(image_target):
                break
            if self.click(click_target, interval=0.5):
                pass

        # 开始循环
        while 1:
            self.screenshot()

            if not self.appear(self.I_S_CHECK_SOUGENBI):
                continue
            if self.current_count >= con.sougenbi_config.limit_count:
                logger.info('Sougenbi count limit out')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('Sougenbi time limit out')
                break
            ticket = number_target.ocr(self.device.image)
            if ticket == 0:
                break

            # 点击挑战
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_S_FIRE, interval=1):
                    pass
                if not self.appear(self.I_S_FIRE):
                    self.run_general_battle(config=con.general_battle_config)
                    break

        # 回去到探索大世界
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_EXPLORATION):
                break
            if self.appear_then_click(self.I_UI_BACK_BLUE, interval=1):
                continue
        logger.info('Back to exploration')

        if s_con.buff_enable:
            self.ui_get_current_page()
            self.ui_goto(page_main)
            self.open_buff()
            if s_con.buff_gold_50_click:
                self.gold_50(False)
            if s_con.buff_gold_100_click:
                self.gold_100(False)
            if s_con.buff_exp_50_click:
                self.exp_50(False)
            if s_con.buff_exp_100_click:
                self.exp_100(False)
            self.close_buff()

        self.set_next_run("Sougenbi", success=True, finish=True)
        raise TaskEnd







if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('test')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
    # print(t.appear(t.I_S_FOOLERY, threshold=0.97))

