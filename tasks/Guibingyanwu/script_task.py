# This Python file uses the following encoding: utf-8
# 鬼兵演武
# @author YLXJ
# github https://github.com/yiliangxiajiao
from datetime import datetime, timedelta

from module.logger import logger
from module.exception import TaskEnd

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records, page_guibingyanwu
from tasks.Guibingyanwu.assets import GuibingyanwuAssets
from tasks.Guibingyanwu.config import Guibingyanwu


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, GuibingyanwuAssets):
    def run(self):
        con: Guibingyanwu = self.config.guibingyanwu
        self.limit_count = con.guibingyanwu_config.limit_count
        limit_time = con.guibingyanwu_config.limit_time
        self.limit_time: timedelta = timedelta(
            hours=limit_time.hour, minutes=limit_time.minute, seconds=limit_time.second
        )
        self.screenshot()
        self.ui_get_current_page()
        # 切换御魂
        if con.switch_soul_config.enable:
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(con.switch_soul_config.switch_group_team)
        # 前往鬼兵演武界面
        self.ui_goto(page_guibingyanwu)
        # 开启加成
        if con.guibingyanwu_config.buff_exp_50_click or con.guibingyanwu_config.buff_exp_100_click:
            self.open_buff(self.I_GBYW_BUFF)
            if con.guibingyanwu_config.buff_exp_50_click:
                self.exp_50(is_open=True)
            if con.guibingyanwu_config.buff_exp_100_click:
                self.exp_100(is_open=True)
            self.close_buff(self.I_GBYW_BUFF)
        # 按照配置锁定队伍
        self.check_lock(
            con.general_battle_config.lock_team_enable,
            self.I_GBYW_LOCK,
            self.I_GBYW_UNLOCK,
        )
        # 开始循环
        success = True
        while 1:
            self.screenshot()
            while not self.ui_page_appear(page_guibingyanwu):
                self.screenshot()
            # 鬼兵部等级>=40时退出
            if self.gbyw_level_enough():
                logger.info("Guibingyanwu level is enough")
                self.config.close_task("Guibingyanwu")
                break
            # 是否达到指定时间或次数
            if self.current_count >= self.limit_count:
                logger.info("Guibingyanwu count limit out")
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info("Guibingyanwu time limit out")
                break
            # 点击挑战
            self.ui_click_until_disappear(self.I_GBYW_FIRE, interval=1)
            # 等待战斗结束
            if self.run_general_battle(config=con.general_battle_config):
                logger.info("Battle success")
            else:
                # 失败
                logger.error("Battle failed, turn off task")
                success = False
                break

        # 关闭加成
        if con.guibingyanwu_config.buff_exp_50_click or con.guibingyanwu_config.buff_exp_100_click:
            self.open_buff(self.I_GBYW_BUFF)
            if con.guibingyanwu_config.buff_exp_50_click:
                self.exp_50(is_open=False)
            if con.guibingyanwu_config.buff_exp_100_click:
                self.exp_100(is_open=False)
            self.close_buff(self.I_GBYW_BUFF)

        self.set_next_run(task="Guibingyanwu", success=success, finish=True)
        raise TaskEnd

    # 检测鬼兵部等级是否高于40
    def gbyw_level_enough(self) -> bool:
        level = self.O_GBYW_LEVEL.ocr(self.device.image)
        level = level % 100
        return level >= 40


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    c = Config("oas1")
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
