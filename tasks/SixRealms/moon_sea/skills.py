import time

from cached_property import cached_property

from module.logger import logger
from tasks.base_task import BaseTask
from tasks.SixRealms.assets import SixRealmsAssets


class MoonSeaSkills(BaseTask, SixRealmsAssets):


    def in_main(self, screenshot: bool = False):
        if screenshot:
            self.screenshot()
        if self.appear(self.I_M_STORE):
            return True
        if self.appear(self.I_M_STORE_ACTIVITY):
            return True
        if self.appear(self.I_BOSS_FIRE):
            return True
        return False

    def battle_lock_team(self):
        self.ui_click(self.I_BATTLE_TEAM_UNLOCK, self.I_BATTLE_TEAM_LOCK)
        return

    def island_battle(self):
        # 小怪战斗
        self.screenshot()
        while 1:
            self.screenshot()
            if self.appear(self.I_SKILL_REFRESH):
                break
            if self.appear(self.I_COIN):
                break
            if self.appear_then_click(self.I_NPC_FIRE, interval=1):
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')
                continue
        self.device.stuck_record_clear()

    @cached_property
    def selects_button(self):
        return [
            self.I_SELECT_0,
            self.I_SELECT_1,
            self.I_SELECT_2,
            self.I_SELECT_3,
        ]

    def _select_skill(self) -> int:
        self.screenshot()
        select = 3  # 从0开始计数
        button = None
        if button is None and self.appear(self.I_SKILL101):
            button = self.I_SKILL101
        elif button is None and self.appear(self.I_SKILL102):
            button = self.I_SKILL102
        # elif button is None and self.appear(self.I_SKILL103):
        #     button = self.I_SKILL103
        # elif button is None and self.appear(self.I_SKILL104):
        #     button = self.I_SKILL104
        if button is not None:
            x, y = button.front_center()
            if x < 360:
                select = 0
            elif 360 <= x < 640:
                select = 1
            elif 640 <= x < 960:
                select = 2
            else:
                select = 3
        logger.info(f'Select {select}')
        return select

    def select_skill(self):
        # 战斗结束后选技能
        logger.info('Start select skill')

        while 1:
            self.screenshot()
            if self.in_main():
                break

            if self.appear(self.I_SKILL_REFRESH):
                select = self._select_skill()
                if self.appear_then_click(self.selects_button[select]):
                    time.sleep(1)
                    # TODO 两次选的间隔太短就直接跳过了，或者说动画没有显示中间的就跳过了
                    continue
            if self.appear_then_click(self.I_COIN, action=self.C_UI_REWARD, interval=1.5):
                continue


