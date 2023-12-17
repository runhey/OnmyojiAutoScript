# This Python file uses the following encoding: utf-8

import time
import random
from datetime import datetime, timedelta
from module.base.utils import point2str
from module.exception import TaskEnd
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_kekkai_toppa
from tasks.RealmRaid.assets import RealmRaidAssets
from tasks.DevRyouToppa.assets import DevRyouToppaAssets
from module.atom.image_grid import ImageGrid
from module.logger import logger
from tasks.Secret.assets import SecretAssets

default_index = [0, 1, 2, 3, 4, 5, 6, 7]
area_map = (
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_1_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_1_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_1,
        "finished_sign": (DevRyouToppaAssets.I_AREA_1_FINISHED, DevRyouToppaAssets.I_AREA_1_FINISHED_NEW)
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_2_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_2_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_2,
        "finished_sign": (DevRyouToppaAssets.I_AREA_2_FINISHED, DevRyouToppaAssets.I_AREA_2_FINISHED_NEW)
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_3_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_3_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_3,
        "finished_sign": (DevRyouToppaAssets.I_AREA_3_FINISHED, DevRyouToppaAssets.I_AREA_3_FINISHED_NEW)
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_4_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_4_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_4,
        "finished_sign": (DevRyouToppaAssets.I_AREA_4_FINISHED, DevRyouToppaAssets.I_AREA_4_FINISHED_NEW)
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_5_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_5_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_5,
        "finished_sign": (DevRyouToppaAssets.I_AREA_5_FINISHED, DevRyouToppaAssets.I_AREA_5_FINISHED_NEW)
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_6_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_6_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_6,
        "finished_sign": (DevRyouToppaAssets.I_AREA_6_FINISHED, DevRyouToppaAssets.I_AREA_6_FINISHED_NEW)
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_7_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_7_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_7,
        "finished_sign": (DevRyouToppaAssets.I_AREA_7_FINISHED, DevRyouToppaAssets.I_AREA_7_FINISHED_NEW)
    },
    {
        "fail_sign": (DevRyouToppaAssets.I_AREA_8_IS_FAILURE_NEW, DevRyouToppaAssets.I_AREA_8_IS_FAILURE),
        "rule_click": DevRyouToppaAssets.C_AREA_8,
        "finished_sign": (DevRyouToppaAssets.I_AREA_8_FINISHED, DevRyouToppaAssets.I_AREA_8_FINISHED_NEW)
    }
)


def random_delay(min_value: float = 1.0, max_value: float = 2.0, decimal: int = 1):
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

        # 确认进入结界突破界面
        self.wait_until_appear(self.I_TOPPA_RECORD)
        if not self.area_index:
            self.area_index.extend(default_index)
        index = 0

        # 开始突破
        while True:
            res = self.attack_area(index)
            # 如果战斗失败或区域不可用，则弹出当前区域索引，开始进攻下一个
            if not res:
                try:
                    self.area_index.pop(0)
                    index = self.area_index[0]
                except IndexError:
                    # 每次出现 IndexError 说明8个区域都不可用，需要滚动列表。
                    self.area_index.extend(default_index)
                    self.flush_area_cache()
                    index = 0

    def check_area(self, index: int):
        """
        检查该区域是否攻略失败
        :return:
        """
        f1, f2 = area_map[index].get("fail_sign")
        f3, f4 = area_map[index].get("finished_sign")
        self.screenshot()
        # 如果该区域已经被攻破则退出
        # Ps: 这时候能打过的都打过了，没有能攻打的结界了, 代表任务已经完成，set_next_run time=1d
        if self.appear(f3, threshold=0.8) or self.appear(f4, threshold=0.8):
            self.set_next_run(task='DevRyouToppa', finish=True, success=True)
            raise TaskEnd
        # 如果该区域攻略失败返回 False
        if self.appear(f1, threshold=0.8) or self.appear(f2, threshold=0.8):
            logger.info('Area [%s] is futile attack, skip.' % str(index + 1))
            return False
        return True

    def attack_area(self, index: int):
        """
        :return: 战斗成功(True) or 战斗失败(False) or 区域不可用（False） or 没有进攻机会（设定下次运行并退出）
        """
        # 先判断是否有进攻机会, 如果没有，set_next_run ，时间等于 (30-60) 分钟后的随机时间
        if not self.has_ticket():
            logger.info("We have no chance to attack. Try again after 1 hour.")
            target = datetime.now() + timedelta(minutes=random.randint(30, 59), seconds=random.randint(1, 59))
            self.set_next_run(task='DevRyouToppa', success=True, target=target)
            raise TaskEnd
        # 每次进攻前检查区域可用性
        if not self.check_area(index):
            return False

        # 正式进攻会设定 2s - 10s 的随机延迟，避免攻击间隔及其相近被检测为脚本。
        delay = random_delay()
        time.sleep(delay)
        rcl = area_map[index].get("rule_click")
        # 点击攻击区域，等待攻击按钮出现。
        self.ui_click(rcl, stop=RealmRaidAssets.I_FIRE)

        # 塔塔开！
        while True:
            self.screenshot()
            # 如果进入战斗
            if self.appear(self.I_EXIT, threshold=0.8):
                logger.info("Start attach area [%s]" % str(index + 1))
                break
            if self.appear(RealmRaidAssets.I_FIRE, threshold=0.8):
                self.appear_then_click(RealmRaidAssets.I_FIRE, threshold=0.8)
                time.sleep(1.5)
                self.screenshot()
                self.appear_then_click(RealmRaidAssets.I_FIRE, threshold=0.8)
                time.sleep(1.5)
                self.screenshot()
                # 点击两次点击后如果还出现进攻按钮则判断该区域已被攻打过
                # 不使用 ocr 的原因是怕不好识别导致重复点击被检测
                if self.appear(self.I_EXIT, threshold=0.8):
                    logger.info("Start attach area [%s]" % str(index + 1))
                    break
                else:
                    self.click(self.C_SAFE_AREA)
                    time.sleep(2)
                return False

        # 等待战斗结束
        # TO-DO 后续更改默认值
        return self.battle_wait(random_click_swipt_enable=True)

    def flush_area_cache(self):
        time.sleep(2)
        duration = 0.352
        count = random.randint(1, 3)
        for i in range(count):
            # 测试过很多次 win32api, win32gui 的 MOUSEEVENTF_WHEEL, WM_MOUSEWHEEL
            # 都出现过很多次离奇的事件，索性放弃了使用以下方法，参数是精心调试的
            # 每次执行刚好刷新一组（2个）设定随机刷新 1 - 3 次
            safe_pos_x = random.randint(540, 1000)
            safe_pos_y = random.randint(320, 540)
            p1 = (safe_pos_x, safe_pos_y)
            p2 = (safe_pos_x, safe_pos_y - 101)
            logger.info('Swipe %s -> %s, %s ' % (point2str(*p1), point2str(*p2), duration))
            self.device.swipe_adb(p1, p2, duration=duration)
            time.sleep(2)

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

    config = Config('oas1')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()
