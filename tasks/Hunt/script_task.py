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
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Hunt.assets import HuntAssets

class ScriptTask(GameUi, GeneralBattle, GeneralRoom, SwitchSoul, HuntAssets):
    kirin_day = True  # 不是麒麟就是阴界之门

    def run(self):
        if not self.check_datetime():
            # 设置下次运行时间 为今天的晚上七点钟
            now = datetime.now()
            next_run_time = datetime.combine(now.date(), time(19, 0, 0))
            self.set_next_run(task='Hunt', success=False, finish=True, target=next_run_time)
            raise TaskEnd('Hunt')
        con = self.config.hunt.hunt_config
        if con.kirin_group_team != '-1,-1' or con.netherworld_group_team != '-1,-1':
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            if con.kirin_group_team != '-1,-1':
                self.run_switch_soul(con.kirin_group_team)
            if con.netherworld_group_team != '-1,-1':
                self.run_switch_soul(con.netherworld_group_team)
        self.ui_get_current_page()
        self.ui_goto(page_hunt)

        self.set_next_run(task='Hunt', success=True, finish=True)
        raise TaskEnd('Hunt')

    def check_datetime(self) -> bool:
        """
        检查日期和时间, 会设置是麒麟还是阴界之门
        :return: 符合19:00-21:00的时间返回True, 否则返回False
        """
        now = datetime.now()
        day_of_week = now.weekday()
        if 0 <= day_of_week <= 3:
            self.kirin_day = True
        elif 4 <= day_of_week <= 6:
            self.kirin_day = False


        if time(18, 59) < now.time() < time(21, 1):
            return True
        else:
            logger.warning('Not in the time period')
            return False

    def kirin(self):
        pass

    def netherworld(self):
        pass


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()

