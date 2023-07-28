# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from enum import Enum
from cached_property import cached_property

from module.logger import logger
from module.exception import TaskEnd

from tasks.GameUi.game_ui import GameUi
from tasks.DemonEncounter.assets import DemonEncounterAssets
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig

class LanternClass(Enum):
    BATTLE = 0  # 打怪  --> 无法判断因为怪的图片不一样，用排除法
    BOX = 1  # 开宝箱
    MAIL = 2  # 邮件答题
    REALM = 3  # 打结界
    EMPTY = 4  # 空


class ScriptTask(GameUi, GeneralBattle, DemonEncounterAssets):

    def run(self):
        self.execute_lantern()
        self.execute_boss()

        self.set_next_run(task='DemonEncounter', success=True, finish=False)
        raise TaskEnd('DemonEncounter')


    def execute_boss(self):
        """
        打boss
        :return:
        """
        logger.hr('Start boss battle', 1)
        while 1:
            self.screenshot()
            if self.appear(self.I_BOSS_FIRE):
                break

            if self.appear_then_click(self.I_BOSS_NAMAZU, interval=1):
                continue
            if self.appear_then_click(self.I_BOSS_SHINKIRO, interval=1):
                continue
            if self.appear_then_click(self.I_BOSS_ODOKURO, interval=1):
                continue
            if self.appear_then_click(self.I_BOSS_OBOROGURUMA, interval=1):
                continue
            if self.appear_then_click(self.I_BOSS_TSUCHIGUMO, interval=1):
                continue
            if self.appear_then_click(self.I_BOSS_SONGSTRESS, interval=1):
                continue
            if self.appear_then_click(self.I_DE_BOSS, interval=2.5):
                continue
        logger.info('Boss battle start')
        # 点击集结挑战
        while 1:
            self.screenshot()
            if self.appear(self.I_BOSS_CONFIRM):
                self.ui_click(self.I_BOSS_NO_SELECT, self.I_BOSS_SELECTED)
                self.ui_click(self.I_BOSS_CONFIRM, self.I_BOSS_GATHER)
                break
            if self.appear(self.I_BOSS_GATHER):
                break
            if self.appear_then_click(self.I_BOSS_FIRE, interval=1):
                continue
        logger.info('Boss battle confirm and enter')
        # 等待挑战
        self.wait_until_disappear(self.I_BOSS_GATHER)
        config = self.con
        self.run_general_battle(config)

        # 等待回到挑战boss主界面
        self.wait_until_appear(self.I_BOSS_GATHER)
        while 1:
            self.screenshot()
            if self.appear(self.I_DE_LOCATION):
                break
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                continue
            if self.appear_then_click(self.I_BOSS_BACK_WHITE, interval=1):
                continue
        # 返回到封魔主界面

    def execute_lantern(self):
        """
        点灯笼 四次
        :return:
        """
        # 先点四次
        while 1:
            self.screenshot()
            cu, re, total = self.O_DE_COUNTER.count(self.device.image)
            if cu + re != total:
                logger.warning('Lantern count error')
                continue
            if cu == 0 and re == 4:
                break
            if self.appear_then_click(self.I_DE_FIND, interval=1):
                continue
        # 然后领取红色达摩
        self.ui_get_reward(self.I_DE_RED_DHARMA)
        self.wait_until_appear(self.I_DE_AWARD)
        # 然后到四个灯笼
        match_click = {
            1: self.C_DE_1,
            2: self.C_DE_1,
            3: self.C_DE_1,
            4: self.C_DE_1,
        }
        for i in range(1, 5):
            logger.hr(f'Check lantern {i}', 3)
            lantern_type = self.check_lantern(i)
            match lantern_type:
                case LanternClass.BOX:
                    self._box()
                case LanternClass.MAIL:
                    self._mail()
                case LanternClass.REALM:
                    self._realm()
                case LanternClass.EMPTY:
                    logger.warning(f'Lantern {i} is empty')
                case LanternClass.BATTLE:
                    self._battle()
            time.sleep(1)

    @cached_property
    def con(self) -> GeneralBattleConfig:
        return GeneralBattleConfig()

    def check_lantern(self, index: int=1):
        """
        检查灯笼的类型
        :param index: 四个灯笼，从1开始
        :return:
        """
        match_roi = {
            1: self.C_DE_1.roi_front,
            2: self.C_DE_2.roi_front,
            3: self.C_DE_3.roi_front,
            4: self.C_DE_4.roi_front,
        }
        match_empty = {
            1: self.I_DE_DEFEAT_1,
            2: self.I_DE_DEFEAT_2,
            3: self.I_DE_DEFEAT_3,
            4: self.I_DE_DEFEAT_4,
        }
        self.I_DE_BOX.roi_back = match_roi[index]
        self.I_DE_LETTER.roi_back = match_roi[index]
        target_box = self.I_DE_BOX
        target_letter = self.I_DE_LETTER
        target_empty = match_empty[index]

        # 开始判断
        self.screenshot()
        if self.appear(target_box):
            logger.info(f'Lantern {index} is box')
            return LanternClass.BOX
        elif self.appear(target_letter):
            logger.info(f'Lantern {index} is letter')
            return LanternClass.MAIL
        elif self.appear(target_empty):
            logger.info(f'Lantern {index} is empty')
            return LanternClass.EMPTY
        else:
            # 无法判断是否是战斗的还是结界的
            logger.info(f'Lantern {index} is battle')
            return LanternClass.BATTLE

    def _box(self):
        # 宝箱不领
        pass

    def _mail(self):
        # 答题，还没有碰到过答题的
        pass

    def _battle(self, target_click):
        config = self.con
        while 1:
            self.screenshot()
            if not self.appear(self.I_DE_LOCATION):
                logger.info('Battle Start')
                break
            if self.click(target_click, interval=target_click):
                continue
        if self.run_general_battle(config):
            logger.info('Battle End')

    def _realm(self):
        # 结界
        pass


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from memory_profiler import profile

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
