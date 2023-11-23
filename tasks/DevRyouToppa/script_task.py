# This Python file uses the following encoding: utf-8

import time

from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.RealmRaid.assets import RealmRaidAssets
from tasks.DevRyouToppa.assets import DevRyouToppaAssets
from module.atom.image_grid import ImageGrid
from module.logger import logger

area_tuple = (
    (DevRyouToppaAssets.I_AREA_1_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_1_IS_FAILURE),
    (DevRyouToppaAssets.I_AREA_2_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_2_IS_FAILURE),
    (DevRyouToppaAssets.I_AREA_3_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_3_IS_FAILURE),
    (DevRyouToppaAssets.I_AREA_4_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_4_IS_FAILURE),
    (DevRyouToppaAssets.I_AREA_5_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_5_IS_FAILURE),
    (DevRyouToppaAssets.I_AREA_6_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_6_IS_FAILURE),
    (DevRyouToppaAssets.I_AREA_7_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_7_IS_FAILURE),
    (DevRyouToppaAssets.I_AREA_8_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_8_IS_FAILURE)
)


def validate_area_num(num: int):
    if num < 1 or num > 8:
        logger.error("Invalid area, [1-8]")
        raise Exception("Invalid area")


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, DevRyouToppaAssets):
    medal_grid: ImageGrid = None

    def run(self):
        """
        执行
        :return:
        """
        logger.info("Test Message")
        print(self.check_area(2))

    def check_area(self, area_num: int):
        """
        检查该区域是否攻略失败
        :return:
        """
        validate_area_num(area_num)
        index = area_num - 1
        f1, f2 = area_tuple[index]
        self.screenshot()
        if self.appear(f1, threshold=0.8) or self.appear(f2, threshold=0.8):
            return True
        return False

    def attack_area(self, area_num: int):
        validate_area_num(area_num)
        index = area_num - 1
        self.screenshot()


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas1')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()
