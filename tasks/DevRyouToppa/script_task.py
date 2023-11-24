# This Python file uses the following encoding: utf-8

import time

from module.exception import TaskEnd
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_kekkai_toppa
from tasks.RealmRaid.assets import RealmRaidAssets
from tasks.DevRyouToppa.assets import DevRyouToppaAssets
from tasks.RyouToppa.assets import RyouToppaAssets
from module.atom.image_grid import ImageGrid
from module.logger import logger
from tasks.Secret.assets import SecretAssets

default_index = [0, 1, 2, 3, 4, 5, 6, 7]
area_map = (
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_1_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_1_IS_FAILURE),
        "rule_click": None
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_2_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_2_IS_FAILURE),
        "rule_click": None
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_3_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_3_IS_FAILURE),
        "rule_click": None
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_4_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_4_IS_FAILURE),
        "rule_click": None
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_5_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_5_IS_FAILURE),
        "rule_click": None
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_6_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_6_IS_FAILURE),
        "rule_click": None
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_7_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_7_IS_FAILURE),
        "rule_click": None
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_8_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_8_IS_FAILURE),
        "rule_click": None
    }
)


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, DevRyouToppaAssets):
    medal_grid: ImageGrid = None
    area_index: list = []

    def run(self):
        """
        执行
        :return:
        """
        # options = self.config.dev_ryou_toppa
        self.ui_get_current_page()
        self.ui_goto(page_kekkai_toppa)

        # 判断阴阳寮是否攻破
        while True:
            self.screenshot()
            if self.appear(RyouToppaAssets.I_RYOU_REWARD_90, threshold=0.8, interval=1):
                self.exit()
            if self.appear(RyouToppaAssets.I_RYOU_REWARD, threshold=0.8, interval=1):
                break

        if not self.area_index:
            self.area_index.extend(default_index)

        # 判断突破区域
        while True:
            try:
                idx = self.area_index[0]
                if self.check_area(idx):
                    break
                self.area_index.pop(0)
            except IndexError:
                # 如果当前页面所有结界都攻破失败，则刷新结界列表。
                # TO-DO: 需要鼠标中键滑动接口(随机滑动，步长为2)
                self.flush_area_cache()

        # 开始突破
        while True:
            result = self.attack_area(idx)

    def check_area(self, index: int):
        """
        检查该区域是否攻略失败
        :return:
        """
        f1, f2 = area_map[index].get("fail_sign")
        self.screenshot()
        if self.appear(f1, threshold=0.8) or self.appear(f2, threshold=0.8):
            logger.info('Area [%s] is futile attack, skip.' % index + 1)
            return False
        return True

    def attack_area(self, index: int):
        self.screenshot()
        # TO-DO: 需要更改过程标识
        if not self.appear(RyouToppaAssets.I_RYOU_TOPPA, threshold=0.8):
            raise Exception("Current page is not RyouToppa.")
        rcl = area_map[index].get("rule_click")

        # 点击攻击区域，等待攻击按钮出现。
        while True:
            self.screenshot()
            if self.appear(RealmRaidAssets.I_FIRE, threshold=0.8):
                break
            if self.click(rcl, interval=2):
                continue

        # 塔塔开！
        while True:
            self.screenshot()
            # 如果进入战斗
            if self.appear():
                logger.info("Start attach area [%s]" % index + 1)
                break
            # 如果该结界已经被攻打过（未刷新）则返回攻打失败
            if self.ocr_appear():
                return False
            if self.appear_then_click(RealmRaidAssets.I_FIRE, threshold=0.8, interval=1.5):
                continue

        # 等待战斗结束
        # TO-DO 后续更改默认值
        return self.battle_wait(random_click_swipt_enable=True)

    def flush_area_cache(self):
        self.area_index.extend(default_index)
        pass

    def exit(self, status: int = 0):
        if status == 0:
            logger.info('DevRyouToppa finished.')
            self.set_next_run(task='DevRyouToppa', finish=True, success=True)
        else:
            logger.error('Task DevRyouToppa exited abnormally.')
        raise TaskEnd

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 重写
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        # 战斗过程 随机点击和滑动 防封
        logger.info("Start battle process")
        while 1:
            self.screenshot()
            if self.appear(SecretAssets.I_SE_BATTLE_WIN):
                logger.info('Win battle')
                self.ui_click_until_disappear(SecretAssets.I_SE_BATTLE_WIN)
                return True
            if self.appear_then_click(self.I_WIN, interval=1):
                continue
            if self.appear(self.I_REWARD):
                logger.info('Win battle')
                self.ui_click_until_disappear(self.I_REWARD)
                return True

            if self.appear(self.I_FALSE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas1')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()
