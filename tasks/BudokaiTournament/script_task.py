# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum, auto
from time import sleep
from datetime import datetime, timedelta
import cv2
import numpy as np
import random
from typing import Any
from cached_property import cached_property

from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.ocr import RuleOcr
from module.base.protect import random_sleep
from module.base.timer import Timer
from module.exception import TaskEnd, GameStuckError
from module.logger import logger

from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.config import SwitchSoulConfig, GeneralBattleConfig, ActivityShikigami
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.BaseActivity.config_activity import GeneralClimb
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
import tasks.Component.GeneralBattle.config_general_battle
import tasks.ActivityShikigami.page as game
from tasks.BudokaiTournament.config import BudokaiTournament
from tasks.BudokaiTournament.assets import BudokaiTournamentAssets




class LimitTimeOut(Exception):
    pass


class LimitCountOut(Exception):
    pass


class StateMachine(BaseTask):
    run_idx: int = 0  # 当前爬塔类型
    _count_map = None

    @cached_property
    def conf(self) -> BudokaiTournament:
        return self.config.model.budokai_tournament

    @property
    def climb_type(self) -> str:
        if self.run_idx >= len(self.conf.run_sequence()):
            return self.conf.run_sequence()[-1]
        return self.conf.run_sequence()[self.run_idx]

    @property
    def count_map(self) -> dict[str, int]:
        """
        :return: key: climb type, value: run count
        """
        if not getattr(self, "_count_map", None):
            self._count_map = {climb_type: 0 for climb_type in self.conf.run_sequence()}
        return self._count_map

    # ----------------------------------------------------
    def put_status(self):
        """
        更新全局状态
        """
        def get_count(self) -> int:
            return self.count_map[self.climb_type]

        def get_limit(self) -> int:
            limit = getattr(self.conf.daily_training, f'limit_{self.climb_type}', 0)
            return 0 if not limit else limit

        # # 超过运行时间
        # if self.limit_time is not None and datetime.now() - self.start_time >= self.limit_time:
        #     logger.info(f"Climb type {self.climb_type} time out")
        #     raise LimitTimeOut
        # 次数达到限制
        if get_count(self) >= get_limit(self):
            logger.info(f"Climb type {self.climb_type} count limit reached")
            raise LimitCountOut

    def switch_next(self):
        """
        切换下一种爬塔类型
        :return: True 切换成功 or False
        """
        self.run_idx += 1
        if self.run_idx >= len(self.conf.run_sequence()):
            logger.info('All climbing activities have been completed')
            return False
        # 切换爬塔类型了, 恢复所有状态
        self.current_count = 0
        logger.hr(f'Climb switch to {self.climb_type}', 2)
        return True


class Foot(StateMachine, GameUi, BaseActivity, SwitchSoul, ActivityShikigamiAssets, BudokaiTournamentAssets):

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """
        根据配置判断当前爬塔类型是否锁定阵容, 并执行锁定或解锁
        """
        enable_preset = getattr(battle_conf, f"enable_preset_{self.climb_type}", False)
        if not enable_preset:
            logger.info(f'Lock {self.climb_type} team')
            self.ui_click(self.I_UNLOCK, stop=self.I_LOCK, interval=1.5)
            return
        logger.info(f'Unlock {self.climb_type} team')
        self.ui_click(self.I_LOCK, stop=self.I_UNLOCK, interval=1.5)

    def start_battle(self):
        click_times, max_times = 0, random.randint(4, 8)
        while 1:
            self.screenshot()
            if self.is_in_battle(False):
                break
            if click_times >= max_times:
                logger.warning(f'Climb {self.climb_type} cannot enter, maybe already end, try next')
                return False
            if (self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1) or
                    self.appear_then_click(self.I_UI_CONFIRM, interval=1) ):
                continue
            if self.ocr_appear_click(self.O_FIRE, interval=2) or self.appear_then_click(self.I_IMG3, interval=2)or self.appear_then_click(self.I_IMG4, interval=2):
                click_times += 1
                logger.info(f'Try click fire, remain times[{max_times - click_times}]')
                continue
        # 运行战斗
        return self.run_general_battle(config=self.get_general_battle_conf())

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        func = getattr(self, f'battle_wait_daily_training', self.battle_wait_daily_training)
        return func(random_click_swipt_enable)

    def battle_wait_daily_training(self, random_click_swipt_enable: bool):
        self.C_REWARD_1.name, self.C_REWARD_2.name, self.C_REWARD_3.name = 'C_REWARD', 'C_REWARD', 'C_REWARD'
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info(f"Start {self.climb_type} battle process")
        if self.climb_type ==  'daily_training':
            self.count_map[self.climb_type] = self.current_count
            super_long_timer = None
        else:
            super_long_timer = Timer(270).start()
            super_long_cnt = 0

        while 1:
            self.screenshot()

            # 出现赢的鼓，点击直到消失
            if self.appear_then_click(self.I_WIN, interval=1.8):
                self.ui_click_until_disappear(self.I_DE_WIN, interval=1.5)
                return True
            if self.appear(self.I_FALSE, threshold=0.8):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False
            if self.ui_reward_appear_click():
                continue
            if super_long_timer and super_long_timer.reached_and_reset():
                if super_long_cnt >= 3:
                    raise GameStuckError
                self.click(self.C_RANDOM_CLICK, interval=10)
                self.device.stuck_record_add('BATTLE_STATUS_S')
                logger.info(f"Start click in battle process for 270s")
                super_long_cnt += 1
            # 随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()
        return False

    def battle_wait_cultivation_drills(self, random_click_swipt_enable: bool):
        self.C_REWARD_1.name, self.C_REWARD_2.name, self.C_REWARD_3.name = 'C_REWARD', 'C_REWARD', 'C_REWARD'
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info(f"Start {self.climb_type} battle process")
        while 1:
            self.screenshot()


    def get_general_battle_conf(self) -> tasks.Component.GeneralBattle.config_general_battle.GeneralBattleConfig:
        from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig as gbc
        # self.conf.validate_switch_preset()
        enable_preset = getattr(self.conf.general_battle, f'enable_preset_{self.climb_type}', False)
        group, team = getattr(self.conf.switch_soul_config, f'group_team_{self.climb_type}').split(',')
        return gbc(lock_team_enable=not enable_preset,
                   preset_enable=enable_preset,
                   preset_group=group if enable_preset else 1,
                   preset_team=team if enable_preset else 1,
                   green_enable=getattr(self.conf.general_battle, f'enable_green_{self.climb_type}', False),
                   green_mark=getattr(self.conf.general_battle, f'green_mark_{self.climb_type}'),
                   random_click_swipt_enable=getattr(self.conf.general_battle,
                                                     f'enable_anti_detect_{self.climb_type}',
                                                     False), )

    def random_reward_click(self, exclude_click: list = None, click_now: bool = True) -> RuleClick:
        """
        随机点击
        :param exclude_click: 排除的点击位置
        :param click_now: 是否立即点击
        :return: 随机的点击位置
        """
        options = [self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM]
        if exclude_click:
            options = [option for option in options if option not in exclude_click]
        target = random.choice(options)
        if click_now:
            self.click(target, interval=1.8)
        return target

    def switch_soul(self, enter_button: RuleImage, cur_img: RuleImage):
        conf = self.conf.switch_soul_config
        enable_switch = getattr(conf, f"enable_switch_{self.climb_type}", False)
        enable_by_name = getattr(conf, f"enable_switch_by_name_{self.climb_type}", False)
        if not enable_switch and not enable_by_name:
            return
        logger.hr('Start switch soul', 2)
        # conf.validate_switch_soul()
        self.ui_click(enter_button, stop=self.I_CHECK_RECORDS, interval=1)
        if enable_by_name:
            group, team = getattr(conf, f"group_team_name_{self.climb_type}").split(",")
            self.run_switch_soul_by_name(group, team)
        elif enable_switch:
            group_team = getattr(conf, f"group_team_{self.climb_type}")
            self.run_switch_soul(group_team)
        self.ui_click(self.I_UI_BACK_YELLOW, stop=cur_img, interval=1)

class ScriptTask(Foot):

    def run(self) -> None:
        # self.limit_time: timedelta = self.conf.general_climb.limit_time_v
        #
        for climb_type in self.conf.run_sequence():
            # 进入到活动的主页面，不是具体的战斗页面
            self.ui_get_current_page()
            self.ui_goto(game.page_climb_act)
            try:
                if getattr(self.conf.daily_training, f'limit_{self.climb_type}') > 0:
                    method_func = getattr(self, f'_run_{climb_type}')
                    method_func()
            except LimitCountOut as e:
                self.ui_click(self.I_UI_BACK_YELLOW, stop=self.I_TO_BATTLE_MAIN, interval=1)
            except LimitTimeOut as e:
                break
            finally:
                # 切换下一个爬塔类型
                self.switch_next()

        # 返回庭院
        logger.hr("Exit BudokaiTournament", 2)
        self.ui_get_current_page(False)
        self.ui_goto(game.page_main)
        if self.conf.daily_training.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())
        self.set_next_run(task="BudokaiTournament", success=True)
        raise TaskEnd

    def _run_daily_training(self):
        """
            更新前请先看 ./README.md
        """
        logger.hr(f'Start run climb type PASS', 1)
        self.ui_clicks([self.I_TO_BATTLE_MAIN, self.I_TO_BATTLE_MAIN_2],
                       stop=self.I_CHECK_BATTLE_MAIN, interval=1)
        self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS, self.I_CHECK_BATTLE_MAIN)

        ocr_limit_timer = Timer(1).start()
        click_limit_timer = Timer(4).start()
        while 1:
            self.screenshot()
            self.put_status()
            # --------------------------------------------------------------
            if (self.appear_then_click(self.I_UI_CONFIRM, interval=0.5)
                    or self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=0.5)):
                continue
            if self.ui_reward_appear_click():
                continue
            if not ocr_limit_timer.reached():
                continue
            ocr_limit_timer.reset()
            if not self.ocr_appear(self.O_FIRE):
                continue
            #  --------------------------------------------------------------
            self.lock_team(self.conf.general_battle)
            if not self.check_tickets_enough():
                logger.warning(f'No tickets left, wait for next time')
                break
            if self.conf.daily_training.random_sleep:
                random_sleep(probability=0.2)
            if self.start_battle():
                continue

        self.ui_click(self.I_UI_BACK_YELLOW, stop=self.I_TO_BATTLE_MAIN, interval=1)

    def _run_cultivation_drills(self):
        """
        更新前请先看 ./README.md
        """
        logger.hr(f'Start run climb type BOSS')

        self.ui_clicks([self.I_TO_BATTLE_BOSS],
                       stop=self.I_CHECK_BATTLE_BOSS, interval=1)

        cnt_scout = 0  # 保留
        switch_soul_done = False
        while 1:
            self.screenshot()
            # --------------------------------------------------------------
            if (self.appear_then_click(self.I_UI_CONFIRM, interval=0.5)
                    or self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=0.5)):
                continue
            if self.ui_reward_appear_click():
                continue
            if self.appear_then_click(self.I_IMG2, interval=0.8):
                continue

            # 搜寻
            if self.appear(self.I_IMG1):
                if not self.check_tickets_enough():
                    logger.warning(f'No tickets left, wait for next time')
                    break
                # self.put_status()
                if cnt_scout >= self.conf.daily_training.limit_cultivation_drills:
                    raise LimitCountOut
                # Click search once, then wait for the boss-detail page without
                # sending another input during the page transition.
                if self.appear_then_click(self.I_IMG1, interval=1.5):
                    transition_timer = Timer(10).start()
                    while 1:
                        self.screenshot()
                        if self.appear(self.I_IMG3) or self.appear(self.I_IMG4):
                            logger.info(f'Cultivation drill done, for next time {cnt_scout}')
                            cnt_scout += 1
                            break
                        if transition_timer.reached():
                            logger.warning('Wait cultivation drill boss detail timeout, retry search')
                            break
                continue
            if not (self.appear(self.I_IMG3) or self.appear(self.I_IMG4)):
                continue
            if not switch_soul_done:
                self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS, self.I_BATTLE_MAIN_TO_RECORDS)
                switch_soul_done = True
                continue

            self.lock_team(self.conf.general_battle)
            if not self.check_tickets_enough():
                logger.warning(f'No tickets left, wait for next time')
                if not self.ui_click(self.C_BOSS_DETAIL_CLOSE, stop=self.I_CHECK_BATTLE_BOSS,
                                     interval=1, timeout=10):
                    raise GameStuckError('Unable to close cultivation drills boss detail')
                break
            if self.conf.daily_training.random_sleep:
                random_sleep(probability=0.2)
            if self.start_battle():
                continue

        self.ui_click(self.I_UI_BACK_YELLOW, stop=self.I_TO_BATTLE_BOSS, interval=1)






    def check_tickets_enough(self) -> bool:
        """
        判断当前爬塔门票是否足够
        :return: True 可以运行 or False
        """
        logger.hr(f'Check {self.climb_type} tickets')
        # apper_button = self.O_FIRE if self.climb_type == 'daily_training' else self.I_IMG3
        if self.climb_type == 'daily_training' and not self.wait_until_appear(self.O_FIRE, wait_time=3):
            logger.warning(f'Detect fire fail, try reidentify')
            return False
        self.screenshot()
        remain_times = 0
        if self.climb_type == 'daily_training':
            remain_times = self.O_REMAIN_AP.ocr_digit(self.device.image)
        if self.climb_type == 'cultivation_drills':
            remain_times= self.O_REMAIN_BOSS.ocr_digit(self.device.image)
        return remain_times > 0



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()

