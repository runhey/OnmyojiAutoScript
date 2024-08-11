# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_team, page_shikigami_records
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul


class ScriptTask(GameUi, GeneralBattle, GeneralRoom, GeneralInvite, SwitchSoul):

    def run(self):
        conf = self.config.tako
        if conf.switch_soul.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(conf.switch_soul.switch_group_team)

        if conf.switch_soul.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(conf.switch_soul.group_name,
                                         conf.switch_soul.team_name)
        # 加成
        conf_buff = conf.tako_config
        if conf_buff.enable:
            self.ui_get_current_page()
            self.ui_goto(page_main)
            self.open_buff()
            if conf_buff.buff_gold_50_click:
                self.gold_50()
            if conf_buff.buff_gold_100_click:
                self.gold_100()
            if conf_buff.buff_exp_50_click:
                self.exp_50()
            if conf_buff.buff_exp_100_click:
                self.exp_100()
            self.close_buff()

        # 进入
        self.ui_get_current_page()
        self.ui_goto(page_team)
        if 5 <= self.start_time.weekday() <= 6:
            # 周末
            self.check_zones('喷怒的石距')
        else:
            self.check_zones('石距')
        if not self.create_room():
            self.exit_task()
        self.ensure_public()
        self.create_ensure()
        # 进入到了房间里面
        wait_timer = Timer(60)
        wait_timer.start()
        while 1:
            self.screenshot()

            if not self.is_in_room():
                continue
            if wait_timer.reached():
                logger.warning('Wait for too long, exit')
                self.exit_room()
                break
            if not self.appear(self.I_ADD_1):
                # 有人进来了，可以进行挑战
                logger.info('There is someone in the room and start the challenge')
                self.click_fire()
                self.run_general_battle()
                break
        self.exit_task()

    def exit_task(self):
        """
        退出任务
        :return:
        """
        conf_buff = self.config.tako.tako_config
        self.ui_get_current_page()
        self.ui_goto(page_main)
        if conf_buff.enable:
            self.ui_get_current_page()
            self.ui_goto(page_main)
            self.open_buff()
            if conf_buff.buff_gold_50_click:
                self.gold_50(False)
            if conf_buff.buff_gold_100_click:
                self.gold_100(False)
            if conf_buff.buff_exp_50_click:
                self.exp_50(False)
            if conf_buff.buff_exp_100_click:
                self.exp_100(False)
            self.close_buff()

        self.set_next_run(task='Tako', success=True, finish=False)
        raise TaskEnd('Tako')

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 重写
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        # 战斗过程 随机点击和滑动 防封
        logger.info("Start battle process")
        while 1:
            self.screenshot()
            if self.appear(self.I_WIN) or self.appear(self.I_REWARD):
                logger.info('Win battle')
                self.ui_click_until_disappear(self.I_WIN)
                while 1:
                    self.screenshot()
                    if self.appear(self.I_CHECK_MAIN) or self.appear(self.I_CHECK_TEAM):
                        break
                    if self.click(self.C_REWARD_2, interval=2):
                        continue
                return True

            if self.appear(self.I_FALSE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()



