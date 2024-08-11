# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
from datetime import datetime, timedelta
import random

from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.RyouToppa.assets import RyouToppaAssets
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.config_base import ConfigBase, Time
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_realm_raid, page_main, page_kekkai_toppa, page_shikigami_records
from tasks.RealmRaid.assets import RealmRaidAssets

from module.logger import logger
from module.exception import TaskEnd
from module.atom.image_grid import ImageGrid
from module.base.utils import point2str
from module.base.timer import Timer
from module.exception import GamePageUnknownError



area_map = (
    {
        "fail_sign": (RyouToppaAssets.I_AREA_1_IS_FAILURE_NEW, RyouToppaAssets.I_AREA_1_IS_FAILURE),
        "rule_click": RyouToppaAssets.C_AREA_1,
        "finished_sign": (RyouToppaAssets.I_AREA_1_FINISHED, RyouToppaAssets.I_AREA_1_FINISHED_NEW)
    },
    {
        "fail_sign": (RyouToppaAssets.I_AREA_2_IS_FAILURE_NEW, RyouToppaAssets.I_AREA_2_IS_FAILURE),
        "rule_click": RyouToppaAssets.C_AREA_2,
        "finished_sign": (RyouToppaAssets.I_AREA_2_FINISHED, RyouToppaAssets.I_AREA_2_FINISHED_NEW)
    },
    {
        "fail_sign": (RyouToppaAssets.I_AREA_3_IS_FAILURE_NEW, RyouToppaAssets.I_AREA_3_IS_FAILURE),
        "rule_click": RyouToppaAssets.C_AREA_3,
        "finished_sign": (RyouToppaAssets.I_AREA_3_FINISHED, RyouToppaAssets.I_AREA_3_FINISHED_NEW)
    },
    {
        "fail_sign": (RyouToppaAssets.I_AREA_4_IS_FAILURE_NEW, RyouToppaAssets.I_AREA_4_IS_FAILURE),
        "rule_click": RyouToppaAssets.C_AREA_4,
        "finished_sign": (RyouToppaAssets.I_AREA_4_FINISHED, RyouToppaAssets.I_AREA_4_FINISHED_NEW)
    },
    {
        "fail_sign": (RyouToppaAssets.I_AREA_5_IS_FAILURE_NEW, RyouToppaAssets.I_AREA_5_IS_FAILURE),
        "rule_click": RyouToppaAssets.C_AREA_5,
        "finished_sign": (RyouToppaAssets.I_AREA_5_FINISHED, RyouToppaAssets.I_AREA_5_FINISHED_NEW)
    },
    {
        "fail_sign": (RyouToppaAssets.I_AREA_6_IS_FAILURE_NEW, RyouToppaAssets.I_AREA_6_IS_FAILURE),
        "rule_click": RyouToppaAssets.C_AREA_6,
        "finished_sign": (RyouToppaAssets.I_AREA_6_FINISHED, RyouToppaAssets.I_AREA_6_FINISHED_NEW)
    },
    {
        "fail_sign": (RyouToppaAssets.I_AREA_7_IS_FAILURE_NEW, RyouToppaAssets.I_AREA_7_IS_FAILURE),
        "rule_click": RyouToppaAssets.C_AREA_7,
        "finished_sign": (RyouToppaAssets.I_AREA_7_FINISHED, RyouToppaAssets.I_AREA_7_FINISHED_NEW)
    },
    {
        "fail_sign": (RyouToppaAssets.I_AREA_8_IS_FAILURE_NEW, RyouToppaAssets.I_AREA_8_IS_FAILURE),
        "rule_click": RyouToppaAssets.C_AREA_8,
        "finished_sign": (RyouToppaAssets.I_AREA_8_FINISHED, RyouToppaAssets.I_AREA_8_FINISHED_NEW)
    }
)


def random_delay(min_value: float = 1.0, max_value: float = 2.0, decimal: int = 1):
    """
    生成一个指定范围内的随机小数
    """
    random_float_in_range = random.uniform(min_value, max_value)
    return (round(random_float_in_range, decimal))

class ScriptTask(GeneralBattle, GameUi, SwitchSoul, RyouToppaAssets):
    medal_grid: ImageGrid = None

    def run(self):
        """
        执行
        :return:
        """
        ryou_config = self.config.ryou_toppa
        time_limit: Time = ryou_config.raid_config.limit_time
        time_delta = timedelta(hours=time_limit.hour, minutes=time_limit.minute, seconds=time_limit.second)
        self.medal_grid = ImageGrid([RealmRaidAssets.I_MEDAL_5, RealmRaidAssets.I_MEDAL_4, RealmRaidAssets.I_MEDAL_3,
                                     RealmRaidAssets.I_MEDAL_2, RealmRaidAssets.I_MEDAL_1, RealmRaidAssets.I_MEDAL_0])

        if ryou_config.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(ryou_config.switch_soul_config.switch_group_team)

        if ryou_config.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(ryou_config.switch_soul_config.group_name, ryou_config.switch_soul_config.team_name)

        self.ui_get_current_page()
        self.ui_goto(page_kekkai_toppa)
        ryou_toppa_start_flag = True
        ryou_toppa_success_penetration = False
        # 点击突破
        while 1:
            self.screenshot()
            if self.appear_then_click(RealmRaidAssets.I_REALM_RAID, interval=1):
                continue
            if self.appear(self.I_REAL_RAID_REFRESH, threshold=0.8):
                if self.appear_then_click(self.I_RYOU_TOPPA, interval=1):
                    continue
            # 攻破阴阳寮，说明寮突已开，则退出
            elif self.appear(self.I_SUCCESS_PENETRATION, threshold=0.8):
                ryou_toppa_start_flag = True
                ryou_toppa_success_penetration = True
                break
            # 出现选择寮突说明寮突未开
            elif self.appear(self.I_SELECT_RYOU_BUTTON, threshold=0.8):
                ryou_toppa_start_flag = False
                break
            # 出现寮奖励， 说明寮突已开
            elif self.appear(self.I_RYOU_REWARD, threshold=0.8) or self.appear(self.I_RYOU_REWARD_90, threshold=0.8):
                ryou_toppa_start_flag = True
                break

        logger.attr('ryou_toppa_start_flag', ryou_toppa_start_flag)
        logger.attr('ryou_toppa_success_penetration', ryou_toppa_success_penetration)
        # 寮突未开 并且有权限， 开开寮突
        if not ryou_toppa_start_flag and ryou_config.raid_config.ryou_access:
            # 作为寮管理，开启今天的寮突
            logger.info("As the manager of the ryou, try to start ryou toppa.")
            self.start_ryou_toppa()

        # 100% 攻破, 第二天再执行
        if ryou_toppa_success_penetration:
            self.set_next_run(task='RyouToppa', finish=True, success=True)
            raise TaskEnd
        if self.config.ryou_toppa.general_battle_config.lock_team_enable:
            logger.info("Lock team.")
            self.ui_click(self.I_TOPPA_UNLOCK_TEAM, self.I_TOPPA_LOCK_TEAM)
        else:
            logger.info("Unlock team.")
            self.ui_click(self.I_TOPPA_LOCK_TEAM, self.I_TOPPA_UNLOCK_TEAM)
        # --------------------------------------------------------------------------------------------------------------
        # 开始突破
        # --------------------------------------------------------------------------------------------------------------
        area_index = 0
        success = True
        while 1:
            if not self.has_ticket():
                logger.info("We have no chance to attack. Try again after 1 hour.")
                success = False
                break
            if self.current_count >= ryou_config.raid_config.limit_count:
                logger.warning("We have attacked the limit count.")
                break
            if datetime.now() >= self.start_time + time_delta:
                logger.warning("We have attacked the limit time.")
                break
            # 进攻
            res = self.attack_area(area_index)
            # 如果战斗失败或区域不可用，则弹出当前区域索引，开始进攻下一个
            if not res:
                area_index += 1
                if area_index >= len(area_map):
                    logger.warning('All areas are not available, it will flush the area cache')
                    area_index = 0
                    self.flush_area_cache()
                continue


        # 回 page_main 失败
        # self.ui_current = page_ryou_toppa
        # self.ui_goto(page_main)
        if success:
            self.set_next_run(task='RyouToppa', finish=True, server=True, success=True)
        else:
            self.set_next_run(task='RyouToppa', finish=True, server=True, success=False)
        raise TaskEnd

    def start_ryou_toppa(self):
        """
        开启寮突破
        :return:
        """
        # 点击寮突
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_SELECT_RYOU_BUTTON, interval=1):
                break
        logger.info(f'Click {self.I_SELECT_RYOU_BUTTON.name}')

        # 选择第一个寮
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_GUILD_ORDERS_REWARDS, action=self.C_SELECT_FIRST_RYOU, interval=1):
                break
        logger.info(f'Click {self.C_SELECT_FIRST_RYOU.name}')

        # 点击开始突入
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_START_TOPPA_BUTTON, interval=1):
                continue
            # 出现寮奖励， 说明寮突已开
            if self.appear(self.I_RYOU_REWARD, threshold=0.8):
                break
        logger.info(f'Click {self.I_START_TOPPA_BUTTON.name}')

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

    def check_area(self, index: int) -> bool:
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
            self.set_next_run(task='RyouToppa', finish=True, success=True)
            raise TaskEnd
        # 如果该区域攻略失败返回 False
        if self.appear(f1, threshold=0.8) or self.appear(f2, threshold=0.8):
            logger.info('Area [%s] is futile attack, skip.' % str(index + 1))
            return False
        return True

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

    def attack_area(self, index: int):
        """
        :return: 战斗成功(True) or 战斗失败(False) or 区域不可用（False） or 没有进攻机会（设定下次运行并退出）
        """
        # 每次进攻前检查区域可用性
        if not self.check_area(index):
            return False

        # 正式进攻会设定 2s - 10s 的随机延迟，避免攻击间隔及其相近被检测为脚本。
        if self.config.ryou_toppa.raid_config.random_delay:
            delay = random_delay()
            time.sleep(delay)


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
                time.sleep(1)
                self.screenshot()
                if self.appear(self.I_TOPPA_RECORD, threshold=0.85):
                    continue
                logger.info("Start attach area [%s]" % str(index + 1))
                return self.run_general_battle(config=self.config.ryou_toppa.general_battle_config)

            if self.appear_then_click(RealmRaidAssets.I_FIRE, interval=2, threshold=0.8):
                click_failure_count += 1
                continue
            if self.click(rcl, interval=5):
                continue


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas1')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()
