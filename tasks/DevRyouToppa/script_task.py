# This Python file uses the following encoding: utf-8

import time
import random
from datetime import datetime
from module.base.utils import point2str
from module.exception import TaskEnd
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
        "rule_click": DevRyouToppaAssets.C_AREA_1,
        "finished_sign": DevRyouToppaAssets.I_AREA_1_FINISHED
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_2_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_2_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_2,
        "finished_sign": DevRyouToppaAssets.I_AREA_2_FINISHED
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_3_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_3_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_3,
        "finished_sign": DevRyouToppaAssets.I_AREA_3_FINISHED
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_4_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_4_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_4,
        "finished_sign": DevRyouToppaAssets.I_AREA_4_FINISHED
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_5_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_5_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_5,
        "finished_sign": DevRyouToppaAssets.I_AREA_5_FINISHED
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_6_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_6_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_6,
        "finished_sign": DevRyouToppaAssets.I_AREA_6_FINISHED
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_7_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_7_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_7,
        "finished_sign": DevRyouToppaAssets.I_AREA_7_FINISHED
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_8_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_8_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_8,
        "finished_sign": DevRyouToppaAssets.I_AREA_8_FINISHED
    }
)


def random_delay(min_value: float = 2.0, max_value: float = 10.0, decimal: int = 1):
    """
    生成一个指定范围内的随机小数
    """
    random_float_in_range = random.uniform(min_value, max_value)
    return (round(random_float_in_range, decimal))


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, DevRyouToppaAssets):
    medal_grid: ImageGrid = None
    area_index: list = []

    def run(self):
        """
        执行
        :return:
        """

        options = self.config.dev_ryou_toppa
        self.ui_get_current_page()
        self.ui_goto(page_kekkai_toppa)

        # 判断阴阳寮是否攻破
        while True:
            self.screenshot()
            if self.appear(RyouToppaAssets.I_RYOU_REWARD_90, threshold=0.8):
                self.exit()
            if self.appear(RyouToppaAssets.I_RYOU_REWARD, threshold=0.8):
                break

        if not self.area_index:
            self.area_index.extend(default_index)

        index = self.get_available_area()

        # 开始突破
        while True:
            win = self.attack_area(index)
            delay = random_delay()
            time.sleep(delay)
            if not win:
                try:
                    idx = self.area_index.index(index)
                    index = self.area_index[idx + 1]
                except IndexError:
                    self.flush_area_cache()
                    index = self.get_available_area()

    def get_available_area(self):
        """
        判断突破区域(忽略失败的目标)
        :return: index
        """
        while True:
            try:
                index = self.area_index[0]
                if self.check_area(index):
                    return index
                self.area_index.pop(0)
            except IndexError:
                # 如果当前页面所有结界都攻破失败，则刷新结界列表。
                self.flush_area_cache()

    def check_area(self, index: int):
        """
        检查该区域是否攻略失败
        :return:
        """
        f1, f2 = area_map[index].get("fail_sign")
        f3 = area_map[index].get("finished_sign")
        self.screenshot()
        # 如果该区域已经被攻破则退出
        # Ps: 这时候能打过的都打过了，没有能攻打的结界了
        if self.appear(f3):
            self.exit()

        # 如果该区域攻略失败返回 False
        if self.appear(f1, threshold=0.8) or self.appear(f2, threshold=0.8):
            logger.info('Area [%s] is futile attack, skip.' % str(index + 1))
            return False
        return True

    def attack_area(self, index: int):
        """
        检查该区域是否攻略失败
        :return: 战斗成功(True) 或 战斗失败(False)
        """
        while True:
            if self.has_ticket():
                break
            time.sleep(60)
        self.screenshot()
        if not self.appear(self.I_TOPPA_RECORD, threshold=0.8):
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
            if self.appear(self.I_EXIT, threshold=0.8):
                logger.info("Start attach area [%s]" % str(index + 1))
                break
            if self.appear_then_click(RealmRaidAssets.I_FIRE, threshold=0.8):
                time.sleep(1.5)
                self.screenshot()
                self.appear_then_click(RealmRaidAssets.I_FIRE, threshold=0.8)
                time.sleep(1.5)
                self.screenshot()
                # 点击两次点击后如果还出现进攻按钮则判断该区域已被攻打过
                # 不使用 ocr 的原因是怕不好识别导致重复点击被检测
                if self.appear(RealmRaidAssets.I_FIRE):
                    return False
                continue

        # 等待战斗结束
        # TO-DO 后续更改默认值
        return self.battle_wait(random_click_swipt_enable=True)

    def flush_area_cache(self):
        time.sleep(2)
        self.area_index.extend(default_index)
        duration = 0.352
        count = random.randint(1, 3)
        for i in range(count):
            safe_pos_x = random.randint(540, 1000)
            safe_pos_y = random.randint(320, 540)
            p1 = (safe_pos_x, safe_pos_y)
            p2 = (safe_pos_x, safe_pos_y - 101)
            logger.info('Swipe %s -> %s, %s ' % (point2str(*p1), point2str(*p2), duration))
            self.device.swipe_adb(p1, p2, duration=duration)
            time.sleep(2)

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

    def has_ticket(self) -> bool:
        """
        如果没有票了，那么就返回False
        :return:
        """
        # 21点后无限进攻机会
        if datetime.now().hour >= 21:
            return True
        self.wait_until_appear(self.I_TOPPA_RECORD)
        self.screenshot()
        cu, res, total = self.O_NUMBER.ocr(self.device.image)
        if cu == 0 and cu + res == total:
            logger.warning(f'Execute round failed, no ticket')
            return False
        return True


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas2')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()
