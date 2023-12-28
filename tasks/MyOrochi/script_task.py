# This Python file uses the following encoding: utf-8
import time

import random
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.DevExploration.assets import DevExplorationAssets
from tasks.MyOrochi.assets import MyOrochiAssets
from module.logger import logger
from tasks.MyOrochi.config import RoleMode

safe_click = (MyOrochiAssets.C_SAFE_AREA_1, MyOrochiAssets.C_SAFE_AREA_2)


def random_delay(min_value: float = 1.0, max_value: float = 2.0, decimal: int = 1):
    """
    生成一个指定范围内的随机小数
    """
    random_float_in_range = random.uniform(min_value, max_value)
    return (round(random_float_in_range, decimal))


class ScriptTask(GeneralBattle, GameUi, DevExplorationAssets):

    def run(self):
        options = self.config.my_orochi
        if options.orochi_config.mode == RoleMode.CAPTAIN:
            logger.info("Run Role: %s" % str(options.orochi_config.mode))
            return self._run_captain()
        elif options.orochi_config.mode == RoleMode.MEMBER:
            logger.info("Run Role: %s" % str(options.orochi_config.mode))
            return self._run_member()
        else:
            logger.exception("Invalid mode, please choice [captain] or [member]")

    def _run_captain(self):
        count = 1
        while True:
            self.screenshot()
            if self.in_room():
                self.wait_until_disappear(MyOrochiAssets.I_SECOND_PIT_POSITION)
                # time.sleep(random_delay(0.3, 1, decimal=2))
                self.ui_click_until_disappear(MyOrochiAssets.I_FIRE_SIGN)
            if self.in_fight():
                logger.hr('检测到进入战斗: %s' % str(count), level=1)
                self._run_battle()
                count += 1
            time.sleep(0.2)

    def _run_member(self):
        count = 1
        while True:
            self.screenshot()
            if self.in_fight():
                logger.hr('检测到进入战斗: %s' % str(count), level=1)
                self._run_battle()
                count += 1
            time.sleep(0.2)

    def _run_battle(self):
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        while True:
            self.screenshot()
            if self.appear(MyOrochiAssets.I_GU):
                for i in range(random.randint(2, 4)):
                    self.click(random.choice(safe_click))
                    time.sleep(random_delay(0.08, 0.2, decimal=2))
            if self.appear(MyOrochiAssets.I_ORICHI_END):
                interval = random_delay(0.1, 0.2, decimal=2)
                self.ui_click_u_disappear(click=random.choice(safe_click),
                                          stop=MyOrochiAssets.I_ORICHI_END, interval=interval)
                return True
            if self.appear(MyOrochiAssets.I_ORICHI_GLOD):
                interval = random_delay(0.12, 0.25, decimal=2)
                self.ui_click_u_disappear(click=random.choice(safe_click),
                                          stop=MyOrochiAssets.I_ORICHI_GLOD, interval=interval)
                return True
            if self.appear(self.I_FALSE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False
            time.sleep(0.2)

    def in_fight(self):
        self.screenshot()
        if self.appear(self.I_EXIT):
            return True
        else:
            return False

    def in_room(self):
        self.screenshot()
        if self.appear(MyOrochiAssets.I_IN_ROOM):
            return True
        else:
            return False


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas2')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()
