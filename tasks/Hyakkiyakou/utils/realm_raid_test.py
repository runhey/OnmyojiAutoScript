import time
from datetime import datetime, timedelta
import random

from module.logger import logger

from tasks.RyouToppa.script_task import ScriptTask, area_map
from tasks.RealmRaid.assets import RealmRaidAssets


class RealmRaidTest(ScriptTask):

    def attack_area(self, index: int):
        """
        :return: 战斗成功(True) or 战斗失败(False) or 区域不可用（False） or 没有进攻机会（设定下次运行并退出）
        """

        rcl = area_map[index].get("rule_click")
        # # 点击攻击区域，等待攻击按钮出现。
        # self.ui_click(rcl, stop=RealmRaidAssets.I_FIRE, interval=2)
        # 塔塔开！
        click_failure_count = 0
        while True:
            self.screenshot()
            if click_failure_count >= 3:
                logger.warning("Click failure, check your click position")
                return False
            if not self.appear(self.I_TOPPA_RECORD, threshold=0.85):
                time.sleep(1.5)
                self.screenshot()
                if self.appear(self.I_TOPPA_RECORD, threshold=0.85):
                    continue
                logger.info("Start attach area [%s]" % str(index + 1))
                return self.run_general_battle_back(config=self.config.ryou_toppa.general_battle_config)

            if self.appear_then_click(RealmRaidAssets.I_FIRE, interval=2, threshold=0.8):
                click_failure_count += 1
                continue
            if self.click(rcl, interval=5):
                continue
        self.wait_until_appear(self.I_TOPPA_RECORD)

    def run30(self):
        for i in range(29):
            index = i % 7
            self.attack_area(index)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = RealmRaidTest(c, d)
    t.run30()
