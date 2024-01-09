# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import datetime, time

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Orochi.script_task import ScriptTask as OrochiScriptTask
from tasks.Orochi.config import Layer
from tasks.GameUi.page import page_main, page_soul_zones
from tasks.TrueOrochi.assets import TrueOrochiAssets


class ScriptTask(OrochiScriptTask, TrueOrochiAssets):

    def run(self):
        conf = self.config.true_orochi.true_orochi_config
        if conf.current_success >= 2:
            # 超过两次就说明这周打完了没有必要再打了
            logger.warning('This week is full')
            self.check_times(True)
            raise TaskEnd('TrueOrochi')
        self.ui_get_current_page()
        self.ui_goto(page_soul_zones)
        self.orochi_enter()
        battle = self.check_true_orochi(True)
        if not battle:
            logger.warning('Not find true orochi')
            logger.warning('Try to battle orochi for ten times')
            self.check_layer(Layer.TEN)
            self.check_lock(False)
            count_orochi_ten = 0
            while 1:
                self.screenshot()
                # 检查猫咪奖励
                if self.appear_then_click(self.I_PET_PRESENT, action=self.C_WIN_3, interval=1):
                    continue
                if not self.appear(self.I_OROCHI_FIRE):
                    continue
                if self.check_true_orochi(False):
                    logger.info('Find true orochi')
                    battle = True
                    break
                if count_orochi_ten >= 10:
                    logger.warning('Not find true orochi')
                    battle = False
                    break
                # 否则点击挑战
                if self.appear(self.I_OROCHI_FIRE):
                    self.ui_click_until_disappear(self.I_OROCHI_FIRE)
                    self.run_general_battle()
                    count_orochi_ten += 1
                    continue

        if not battle:
            # 如果还没有真蛇，那么就退出
            self.check_times(battle)
            raise TaskEnd('TrueOrochi')
        # 如果有真蛇，那么就开始战斗
        logger.hr('True Orochi Battle')
        conf.current_success += 1
        while 1:
            self.screenshot()
            if self.appear(self.I_ST_CREATE_ROOM):
                break
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_ST_FIRE, interval=4):
                continue
            if self.appear_then_click(self.I_FIND_TS, interval=1):
                continue
        self.ensure_private()
        while 1:
            self.screenshot()
            if self.appear(self.I_ST_FIRE_PREPARE):
                break
            if self.appear_then_click(self.I_FIRE, interval=3, threshold=0.7):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_ST_CREATE_ROOM, interval=1):
                continue
        # 战斗准备
        logger.info('Battle prepare')
        self.ui_click(self.I_ST_FIRE_PREPARE, self.I_BUFF)
        while 1:
            self.screenshot()
            if not self.appear(self.I_BUFF):
                break
            if self.appear_then_click(self.I_ST_AUTO_FALSE, interval=0.8):
                continue
            if self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=1.8):
                continue
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info("Start battle process")
        check_timer = Timer(280)
        check_timer.start()
        while 1:
            self.screenshot()
            if self.appear(self.I_GREED_GHOST):
                sleep(0.7)
                self.screenshot()
                if not self.appear(self.I_GREED_GHOST):
                    continue
                # 左上角的贪吃鬼
                while 1:
                    self.screenshot()
                    if not self.appear(self.I_GREED_GHOST):
                        break
                    if self.appear_then_click(self.I_GREED_GHOST, interval=1):
                        continue
                    if self.appear_then_click(self.I_ST_FRAME, interval=1):
                        continue
                break
            if self.appear_then_click(self.I_ST_FRAME, interval=1):
                continue
            if check_timer.reached():
                logger.warning('Battle timeout')
                check_timer.reset()
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')
            sleep(0.5)

        logger.info("Battle process end")
        self.check_times(battle)
        raise TaskEnd('TrueOrochi')


    def check_true_orochi(self, screenshot=False) -> bool:
        """
        检查是否出现真蛇（要求当前的界面必须是在御魂挑战的界面）
        :return:
        """
        if screenshot:
            self.screenshot()
        return self.appear(self.I_FIND_TS)

    def check_times(self, battle: bool):
        """
        后续的次数和时间设置
        :param battle:
        :param current_success: 这周的成功次数
        :return:
        """
        now = datetime.now()
        now_year, now_week_number, now_weekday = now.isocalendar()
        if battle:
            next_run = now + self.config.true_orochi.scheduler.success_interval
        else:
            next_run = now + self.config.true_orochi.scheduler.fail_interval
        next_run_year, next_run_week_number, next_run_weekday = next_run.isocalendar()
        self.set_next_run(task='TrueOrochi', target=next_run)
        # 如果下次运行的时间是下一周，那么就重置成功次数
        if now_week_number != next_run_week_number:
            self.config.true_orochi.true_orochi_config.current_success = 0
        else:
            # 如果不是下一周，那么就加一
            self.config.true_orochi.true_orochi_config.current_success += 1






    def run_true_orochi(self) -> bool:
        pass


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()

