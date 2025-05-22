# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import timedelta, datetime, time
from cached_property import cached_property

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_hunt, page_shikigami_records
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Hunt.assets import HuntAssets

class ScriptTask(GameUi, GeneralBattle, GeneralInvite, SwitchSoul, HuntAssets):
    kirin_day = True  # 不是麒麟就是阴界之门
    tomorrow_kirin_day = True  # 明天是麒麟还是阴界之门

    def run(self):
        self.con_time = self.config.hunt.hunt_time
        if not self.check_datetime():
            # 设置下次运行时间 为今天的晚上七点钟
            raise TaskEnd('Hunt')
        con = self.config.hunt.hunt_config
        if con.kirin_group_team != '-1,-1' or con.netherworld_group_team != '-1,-1':
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)

            if self.kirin_day:
                if con.kirin_group_team != '-1,-1':
                    self.run_switch_soul(con.kirin_group_team)
            else:
                if con.netherworld_group_team != '-1,-1':
                    self.run_switch_soul(con.netherworld_group_team)
        self.ui_get_current_page()
        self.ui_goto(page_hunt)

        if self.kirin_day:
            self.kirin()
        else:
            self.netherworld()
        sleep(1)

        self.plan_tomorrow_hunt()
        raise TaskEnd('Hunt')

    def check_datetime(self) -> bool:
        """
        检查日期和时间, 会设置是麒麟还是阴界之门
        :return: 符合麒麟19:00-21:00、阴界19:00-23:00的时间返回True, 否则返回False
        """
        now = datetime.now()
        day_of_week = now.weekday()
        if 0 <= day_of_week <= 3:
            self.kirin_day = True
        elif 4 <= day_of_week <= 6:
            self.kirin_day = False
        
        if 3 <= day_of_week <= 5:
            self.tomorrow_kirin_day = False
        else:
            self.tomorrow_kirin_day = True

        now = datetime.now()
        # 如果时间在00:00-19:00 之间则设定时间为当天的自定义时间，返回False
        if now.time() < time(19, 0):
            if self.kirin_day:
                logger.info('Today is the Kirin day')
                self.custom_next_run(task='Hunt', custom_time=self.con_time.kirin_time, time_delta=0)
            else:
                logger.info('Today is the Netherworld day')
                self.custom_next_run(task='Hunt', custom_time=self.con_time.netherworld_time, time_delta=0)
            raise TaskEnd('Hunt')
        # 如果是麒麟日在21:00-23:59之间则设定时间为明天的自定义时间，返回False
        elif now.time() > time(21, 0) and self.kirin_day:
            self.plan_tomorrow_hunt()
            raise TaskEnd('Hunt')
        # 如果是阴界日在23:00-23:59之间则设定时间为明天的自定义时间，返回False
        elif now.time() > time(23, 0) and not self.kirin_day:
            self.plan_tomorrow_hunt()
            raise TaskEnd('Hunt')
        # 如果是在19:00-21:00之间则返回True
        else:
            return True

    def plan_tomorrow_hunt(self):
        # 安排次日狩猎战，便于复用
        if self.tomorrow_kirin_day:
            logger.info('Tomorrow is the Kirin day')
            self.custom_next_run(task='Hunt', custom_time=self.con_time.kirin_time, time_delta=1)
        else:
            logger.info('Tomorrow is the Netherworld day')
            self.custom_next_run(task='Hunt', custom_time=self.con_time.netherworld_time, time_delta=1)

    def kirin(self):
        logger.hr('kirin', 2)
        # TODO: 没有碰到：（1）麒麟未开 （2）麒麟已经挑战完毕
        while 1:
            self.screenshot()

            if self.appear(self.I_KIRIN_END):
                # 你的阴阳寮已经打过的麒麟了
                logger.warning('Your guild have already challenged the Kirin')
                self.plan_tomorrow_hunt()
                raise TaskEnd('Hunt')
            if self.appear_then_click(self.I_KIRIN_CHALLAGE, interval=0.9):
                break
            if self.click(self.C_HUNT_ENTER, interval=2.9):
                continue
        logger.info('Arrive the Kirin')
        self.ui_click(self.I_KIRIN_CHALLAGE, self.I_KIRIN_GATHER)
        # 等待进入战斗
        # 等待挑战, 5秒也是等
        sleep(5)
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.wait_until_disappear(self.I_KIRIN_GATHER)
        self.device.stuck_record_clear()
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.run_general_battle()


    def netherworld(self):
        logger.hr('netherworld', 2)
        while 1:
            self.screenshot()
            if self.is_in_room(False):
                self.screenshot()
                if not self.appear(self.I_FIRE):
                    continue
                self.click_fire()
                break

            if self.appear_then_click(self.I_NW, interval=0.9):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=0.9):
                continue
            if self.appear_then_click(self.I_NW_CHALLAGE, interval=1.5):
                continue
            if self.appear(self.I_NW_DONE):
                # 今日已挑战
                logger.warning('Today have already challenged the Netherworld')
                self.ui_click_until_disappear(self.I_UI_BACK_RED)
                return
        logger.info('Start battle')
        self.run_general_battle()


    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        """
        重写，
        阴界之门： 胜利后回到狩猎战的主界面
        麒麟： 胜利后回到麒麟的主界面
        :param random_click_swipt_enable:
        :return:
        """
        # if self.kirin_day:
        #     return super().battle_wait(random_click_swipt_enable)

        # 阴界之门
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        # 战斗过程 随机点击和滑动 防封
        logger.info("Start battle process")
        stuck_timer = Timer(180)
        stuck_timer.start()
        while 1:
            self.screenshot()
            if self.appear(self.I_WIN):
                logger.info('Battle win')
                self.ui_click_until_disappear(self.I_WIN)
                return True
            # 如果出现失败 就点击，返回False
            if self.appear(self.I_FALSE, threshold=0.8):
                logger.info("Battle result is false")
                self.ui_click_until_disappear(self.I_FALSE)
                return False
            # 如果三分钟还没打完，再延长五分钟
            if stuck_timer and stuck_timer.reached():
                stuck_timer = None
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')








if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()

