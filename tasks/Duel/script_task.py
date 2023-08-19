# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_duel
from tasks.Duel.config import Duel
from tasks.Duel.assets import DuelAssets

class ScriptTask(GameUi, GeneralBattle, DuelAssets):
    def run(self):
        con = self.config.duel.duel_config
        limit_time = con.limit_time
        self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute,
                                               seconds=limit_time.second)
        self.ui_get_current_page()
        self.ui_goto(page_duel)
        if con.switch_all_soul:
            self.switch_all_soul()

        # 循环
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_REWARD, interval=0.6):
                continue
            if not self.duel_main():
                continue

            if datetime.now() - self.start_time >= self.limit_time:
                # 任务执行时间超过限制时间，退出
                logger.info('Duel task is over time')
                break
            if con.honor_full_exit and self.check_honor():
                # 荣誉满了，退出
                logger.info('Duel task is over honor')
                break
            current_score = self.check_score(con.target_score)
            if not current_score:
                # 分数够了，退出
                logger.info('Duel task is over score')
                break
            self.duel_one(current_score, con.green_enable, con.green_mark)

        # 记得退回去到町中
        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_TOWN)
        self.set_next_run(task='Duel', success=True, finish=False)
        raise TaskEnd('Duel')

    def duel_main(self, screenshot=False) -> bool:
        """
        判断是否斗技主界面
        :return:
        """
        if screenshot:
            self.screenshot()
        return self.appear(self.I_D_HELP)

    def switch_all_soul(self):
        """
        一键切换所有御魂
        :return:
        """
        click_count = 0  # 计数
        while 1:
            self.screenshot()
            if click_count >= 2:
                break

            if self.appear_then_click(self.I_D_TEAM, interval=1):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=0.6):
                continue
            if self.appear_then_click(self.I_D_TEAM_SWTICH, interval=1):
                continue
        logger.info('Souls Switch is complete')
        self.ui_click(self.I_UI_BACK_YELLOW, self.I_D_TEAM)

    def check_honor(self) -> bool:
        """
        检查荣誉是否满了
        :return:
        """
        current, remain, total = self.O_D_HONOR.ocr(self.device.image)
        if current == total and remain == 0:
            return True
        return False

    def check_score(self, target: int) -> int or None:
        """
        检查是否达到目标分数
        :param target: 目标分数
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear(self.I_D_CELEB_STAR) or self.appear(self.I_D_CELEB_HONOR):
                logger.info('You are already a celeb')
                return None
            current_score = self.O_D_SCORE.ocr(self.device.image)
            if current_score < 1200 or current_score > 3000:
                continue
            return current_score if current_score <= target else None

    def duel_one(self, current_score: int, enable: bool=False,
                 mark_mode: GreenMarkType=GreenMarkType.GREEN_MAIN) -> bool:
        """
        进行一次斗技， 返回输赢结果
        :param mark_mode:
        :param enable:
        :param current_score: 当前分数, 不同的分数有不同的战斗界面
        :return:
        """
        while 1:
            self.screenshot()
            if not self.appear(self.I_D_HELP):
                break
            if self.appear_then_click(self.I_D_BATTLE, interval=1):
                continue
            if self.appear_then_click(self.I_D_BATTLE_PROTECT, interval=1.6):
                continue
        # 点击斗技 开始匹配对手
        logger.hr('Duel start match')
        while 1:
            self.screenshot()
            if self.appear(self.I_D_AUTO_ENTRY):
                # 出现自动上阵
                self.ui_click_until_disappear(self.I_D_AUTO_ENTRY)
                logger.info('Duel auto entry')
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')
                self.wait_until_disappear(self.I_D_WORD_BATTLE)
                break
            if current_score <= 1800 and self.appear(self.I_D_PREPARE):
                # 低段位有的准备
                self.ui_click(self.I_D_PREPARE, self.I_D_PREPARE_DONE)
                self.wait_until_disappear(self.I_D_PREPARE_DONE)
                logger.info('Duel prepare')
                break
        # 正式进入战斗
        logger.info('Duel start battle')
        while 1:
            self.screenshot()
            if self.ocr_appear(self.O_D_AUTO, interval=0.4):
                break
            if self.ocr_appear_click(self.O_D_HAND, interval=1):
                continue
            # 如果对方直接秒退，那自己就是赢的
            if self.appear(self.I_D_VICTORY):
                logger.info('Duel battle win')
                self.ui_click_until_disappear(self.I_D_VICTORY)
                return True
        # 绿标
        self.green_mark(enable, mark_mode)
        # 等待结果
        logger.info('Duel wait result')
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        battle_win = True
        swipe_count = 0
        swipe_timer = Timer(270)
        swipe_timer.start()
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_D_BATTLE_DATA, action=self.C_D_BATTLE_DATA, interval=0.6):
                continue
            if self.appear(self.I_FALSE):
                # 打输了
                logger.info('Duel battle lose')
                self.ui_click_until_disappear(self.I_FALSE)
                battle_win = False
                break
            if self.appear(self.I_D_FAIL):
                # 输了
                logger.info('Duel battle lose')
                self.ui_click_until_disappear(self.I_D_FAIL)
                battle_win = False
                break
            if self.appear(self.I_WIN):
                # 打赢了
                logger.info('Duel battle win')
                self.ui_click_until_disappear(self.I_WIN)
                battle_win = True
                break
            if self.appear(self.I_D_VICTORY):
                # 打赢了
                logger.info('Duel battle win')
                self.ui_click_until_disappear(self.I_D_VICTORY)
                battle_win = True
                break

            if swipe_timer.reached():
                swipe_timer.reset()
                if swipe_count >= 2:
                    # 记三次，十五分钟没有结束也没谁了
                    logger.info('Duel battle timeout')
                    battle_win = False
                    break
                swipe_count += 1
                logger.warning('Duel battle stuck, swipe')
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')


        return battle_win




if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
