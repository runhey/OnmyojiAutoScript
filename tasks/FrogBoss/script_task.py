# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from cached_property import cached_property
from datetime import datetime

from module.exception import TaskEnd
from module.logger import logger
from module.atom.image import RuleImage
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from tasks.Component.RightActivity.right_activity import RightActivity
from tasks.Component.config_base import TimeDelta
from tasks.FrogBoss.assets import FrogBossAssets
from tasks.FrogBoss.config import Strategy

class ScriptTask(RightActivity, FrogBossAssets):
    def run(self):
        self.enter(self.I_FROG_BOSS_ENTER)
        # 进入主界面
        while 1:
            self.screenshot()

            # 已经下注
            if self.appear(self.I_BETTED):
                logger.info('You have betted')
                break
            # 休息中
            if self.appear(self.I_FROG_BOSS_REST):
                logger.info('Frog Boss Rest')
                break
            # 竞猜成功
            if self.appear(self.I_BET_SUCCESS):
                logger.info('You bet win')
                self.detect()
                while 1:
                    self.screenshot()
                    if self.appear(self.I_BET_LEFT) and self.appear(self.I_BET_RIGHT):
                        break
                    if self.appear_then_click(self.I_BET_SUCCESS_BOX, interval=1):
                        continue
                    if self.appear_then_click(self.I_NEXT_COMPETITION, interval=4):
                        continue
                continue
            # 竞猜失败
            if self.appear(self.I_BET_FAILURE):
                logger.info('You bet lose')
                self.ui_click_until_disappear(self.I_NEXT_COMPETITION)
                self.detect()
                continue
            # 正式竞猜
            if self.appear(self.I_BET_LEFT) and self.appear(self.I_BET_RIGHT):
                self.do_bet()
                continue

        logger.info('FrogBoss end')
        self.next_run()
        raise TaskEnd('FrogBoss')

    def next_run(self):
        time = self.config.model.frog_boss.frog_boss_config.before_end_frog
        time_delta = TimeDelta(hours=time.hour, minutes=time.minute, seconds=time.second)
        time_now = datetime.now()
        time_set = time_now.replace(minute=0, second=0, microsecond=0)
        if 10 <= time_now.hour < 12:
            time_set = time_set.replace(hour=14)
        elif 12 <= time_now.hour < 14:
            time_set = time_set.replace(hour=16)
        elif 14 <= time_now.hour < 16:
            time_set = time_set.replace(hour=18)
        elif 16 <= time_now.hour < 18:
            time_set = time_set.replace(hour=20)
        elif 18 <= time_now.hour < 20:
            time_set = time_set.replace(hour=22)
        elif 20 <= time_now.hour < 22:
            time_set = time_set.replace(hour=24)
        elif 22 <= time_now.hour < 24:
            day = time_now.day + 1
            time_set = time_set.replace(day=day, hour=12)
        else:
            time_set = time_set.replace(hour=12)

        self.set_next_run(task='FrogBoss', target=time_set - time_delta)

    def do_bet(self):
        logger.hr('do bet', level=2)
        self.screenshot()
        count_left = self.O_LEFT_COUNT.ocr(self.device.image)
        count_right = self.O_RIGHT_COUNT.ocr(self.device.image)
        match self.config.model.frog_boss.frog_boss_config.strategy_frog:
            case Strategy.Majority:
                click_image = self.I_BET_LEFT if count_left > count_right else self.I_BET_RIGHT
            case Strategy.Minority:
                click_image = self.I_BET_LEFT if count_left < count_right else self.I_BET_RIGHT
            case Strategy.Bilibili:
                click_image = self.I_BET_LEFT if count_left > count_right else self.I_BET_RIGHT
            case _:
                raise ValueError(f'Unknown bet mode: {self.config.model.frog_boss.frog_boss_config.strategy_frog}')
        logger.info(f'You strategy is {self.config.model.frog_boss.frog_boss_config.strategy_frog} and bet on {click_image}')
        self.ui_click_until_disappear(click_image)
        gold_30_timer = Timer(10)
        gold_30_timer.start()
        while 1:
            self.screenshot()
            if self.appear(self.I_GOLD_30_CHECK):
                break
            if gold_30_timer.reached():
                logger.info('Gold 30 not appear')
                break
            if self.appear_then_click(self.I_GOLD_30, interval=3):
                continue
        # 正式下注
        logger.info('Formal bet')
        while 1:
            self.screenshot()
            if self.appear(self.I_BETTED):
                break
            if self.appear_then_click(self.I_GOLD_30, interval=2):
                continue
            if self.appear_then_click(self.I_BET_SURE, interval=2):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=2):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=2):
                continue

    def detect(self) -> bool:
        """
        检测是左边赢了还是右边赢的
        :return: True 左边赢了
        """
        if self.appear(self.I_SUCCESS_LEFT) and self.appear(self.I_FAILURE_RIGHT):
            result = True
            logger.info('Left win')
        elif self.appear(self.I_SUCCESS_RIGHT) and self.appear(self.I_FAILURE_LEFT):
            result = False
            logger.info('Right win')
        else:
            result = True
        return result

    def get_bilibili(self) -> RuleImage:
        """
        获取博主的策略选择
        :return:
        """
        pass


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()

