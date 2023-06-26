# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.RealmRaid.assets import RealmRaidAssets
from tasks.RealmRaid.config import RealmRaid, RaidMode, AttackNumber
from module.logger import logger
from module.exception import TaskEnd

class ScriptTask(GeneralBattle, GameUi, RealmRaidAssets):

    def run(self):
        """
        执行
        :return:
        """
        config = self.config.realm_raid
        self.home_explore()

        # 点击突破
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_REALM_RAID, interval=1):
                continue
            if self.appear(self.I_BACK_RED, threshold=0.6):
                break
        logger.info(f'Click {self.I_REALM_RAID.name}')

        # 判断是不是锁定阵容
        if config.general_battle_config.lock_team_enable:
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_UNLOCK, interval=1):
                    continue
                if self.appear_then_click(self.I_UNLOCK_2, interval=1):
                    continue
                if self.appear(self.I_LOCK_2, threshold=0.9):
                    break
                if self.appear(self.I_LOCK, threshold=0.9):
                    break
            logger.info(f'Click {self.I_UNLOCK.name}')
        else:
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_LOCK, interval=1):
                    continue
                if self.appear_then_click(self.I_LOCK_2, interval=1):
                    continue
                if self.appear(self.I_UNLOCK_2, threshold=0.9):
                    break
                if self.appear(self.I_UNLOCK, threshold=0.9):
                    break
            logger.info(f'Click {self.I_LOCK.name}')

        # 判断是只打九次还是打完去
        if config.raid_config.attack_number == AttackNumber.NINE:
            self.execute_round(config)
        else:
            while 1:
                if self.execute_round(config):
                    continue
                else:
                    break

        # 点击 右上角的关闭
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_BACK_RED, interval=1):
                continue
            if self.appear(self.I_REALM_RAID, threshold=0.6):
                break
        logger.info(f'Click {self.I_BACK_RED.name}')

        # 点击左上角的关闭
        self.explore_home()

        self.set_next_run(task='RealmRaid')
        raise TaskEnd


    def is_ticket(self) -> bool:
        """
        如果没有票了，那么就返回False
        :return:
        """
        self.screenshot()
        cu, res, total = self.O_NUMBER.ocr(self.device.image)
        if cu == 0 and cu+res == total:
            logger.warning(f'Execute round failed, no ticket')
            return False
        return True

    def medal_fire(self) -> bool:
        """
        点击勋章
        :return:
        """
        # 点击勋章的挑战 和挑战
        time.sleep(0.2)
        is_click = False
        while 1:
            self.screenshot()

            if self.appear(self.I_FIRE, threshold=0.8):
                break

            if self.appear_then_click(self.I_SOUL_RAID, interval=1.5):
                while 1:
                    self.screenshot()
                    if self.appear_then_click(self.I_SOUL_RAID, interval=1.5):
                        continue
                    if not self.appear(self.I_SOUL_RAID, threshold=0.6):
                        break
                continue

            if is_click:
                continue
            if self.appear_then_click(self.I_MEDAL_5_FROG, interval=1.5):
                is_click = True
                continue
            if self.appear_then_click(self.I_MEDAL_5, interval=1.5):
                is_click = True
                continue
            if self.appear_then_click(self.I_MEDAL_4, interval=1.5):
                is_click = True
                continue
            if self.appear_then_click(self.I_MEDAL_3, interval=1.5):
                is_click = True
                continue
            if self.appear_then_click(self.I_MEDAL_2, interval=1.5):
                is_click = True
                continue
            if self.appear_then_click(self.I_MEDAL_1, interval=1.5):
                is_click = True
                continue
            if self.appear_then_click(self.I_MEDAL_0, interval=1.5):
                is_click = True
                continue
        logger.info(f'Click Medal')

        # 点击挑战
        self.wait_until_appear(self.I_FIRE)
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_FIRE, interval=2):
                continue
            if not self.appear(self.I_FIRE, threshold=0.8):
                break
        logger.info(f'Click {self.I_FIRE.name}')

    def execute_round(self, config: RealmRaid) -> bool:
        """
        执行一轮 除非票不够，一直到到九次
        :return:
        """
        # 如果没有票了，就退出
        if not self.is_ticket():
            return False

        # 判断是退四打九还是全部打
        if config.raid_config.raid_mode == RaidMode.NORMAL:
            logger.info(f'Execute round, retreat four attack nine')
            self.medal_fire()
            self.run_general_battle_back(config.general_battle_config)

            self.medal_fire()
            self.run_general_battle_back(config.general_battle_config)

            self.medal_fire()
            self.run_general_battle_back(config.general_battle_config)

            self.medal_fire()
            self.run_general_battle_back(config.general_battle_config)

        # 打九次
        for i in range(9):
            if not self.is_ticket():
                return False
            self.medal_fire()
            self.run_general_battle(config.general_battle_config)
            self.wait_until_appear(self.I_BACK_RED)

        return True
