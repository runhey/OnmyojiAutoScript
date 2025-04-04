# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.DyeTrials.assets import DyeTrialsAssets
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.Restart.assets import RestartAssets

""" 灵染 试炼 """


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, DyeTrialsAssets):

    def run(self):

        cfg = self.config.dye_trials

        # 自动换御魂
        if cfg.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(cfg.switch_soul_config.switch_group_team)
        if cfg.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(cfg.switch_soul_config.group_name, cfg.switch_soul_config.team_name)

        self.ui_get_current_page()
        self.ui_goto(page_main)

        self.get_all()

        self.ui_get_current_page()
        self.ui_goto(page_main)

        self.set_next_run(task='DyeTrials', success=True, finish=True)
        raise TaskEnd('DyeTrials')

    def get_all(self):
        while 1:
            self.screenshot()
            if self.appear(self.I_FP_CHALLENGE):
                break
            if self.appear_then_click(self.I_FP_ACCESS, interval=0.8):
                continue
            if self.appear_then_click(self.I_FP_ACCESS_1, interval=1.5):
                continue
            if self.appear_then_click(self.I_TOGGLE_BUTTON, interval=3):
                continue
        logger.info('Enter DyeTrials')
        boss_timer = Timer(60)
        boss_timer.start()
        battle_num = 0
        while 1:
            self.screenshot()
            time.sleep(0.1)
            if boss_timer.reached():
                self.config.notifier.push(title='超鬼王', message='识别超时退出')
                break
            # 获得奖励
            if self.ui_reward_appear_click():
                boss_timer.reset()
            if self.appear_then_click(RestartAssets.I_HARVEST_CHAT_CLOSE):
                boss_timer.reset()
                continue
            if self.appear(self.I_FP_CHALLENGE, interval=1):
                cu, res, total = self.O_BATTLE_NUM.ocr(image=self.device.image)
                if cu == total == 50 and cu + res == total:
                    break
                if battle_num >= 50:
                    logger.info(f'Battle {battle_num}, enough battle, break')
                    break
                self.ui_click_until_disappear(self.I_FP_CHALLENGE)
                battle_num += 1
                logger.info(f'Battle num [{battle_num}]')
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')
                boss_timer.reset()
                continue
            if self.appear_then_click(self.I_BATTLE_SUCCESS, interval=1):
                boss_timer.reset()
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('DU')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
