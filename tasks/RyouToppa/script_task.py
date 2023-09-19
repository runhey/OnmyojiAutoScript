# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.RyouToppa.assets import RyouToppaAssets
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_realm_raid, page_main, page_kekkai_toppa, page_shikigami_records
from tasks.RealmRaid.assets import RealmRaidAssets
from module.logger import logger
from module.exception import TaskEnd
from module.atom.image_grid import ImageGrid
from module.base.timer import Timer
from module.exception import GamePageUnknownError
from tasks.RyouToppa.config import RaidMode, AttackNumber, HaveManageAccess, RaidConfig, RyouToppa


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, RyouToppaAssets):
    medal_grid: ImageGrid = None

    def run(self):
        """
        执行
        :return:
        """
        ryou_config = self.config.ryou_toppa
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
                logger.info(f'Click {RealmRaidAssets.I_REALM_RAID.name}')
                continue
            if self.appear(self.I_REAL_RAID_REFRESH, threshold=0.8):
                if self.appear_then_click(self.I_RYOU_TOPPA, interval=1):
                    logger.info(f'Click {self.I_RYOU_TOPPA.name}')
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

        # 寮突未开 并且有权限， 开开寮突
        if not ryou_toppa_start_flag and ryou_config.raid_config.ryou_access == 'yes':
            # 开寮突
            self.start_ryou_toppa()

        # 100% 攻破, 第二天再执行
        if ryou_toppa_success_penetration:
            self.set_next_run(task='RyouToppa', finish=True, success=True)
            raise TaskEnd

        # 开始突破
        while 1:
            if self.execute_round():
                continue
            else:
                break

        # 回 page_main 失败
        # self.ui_current = page_ryou_toppa
        # self.ui_goto(page_main)

        self.set_next_run(task='RyouToppa', finish=True, server=False, success=True)
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

    def is_ticket(self) -> bool:
        """
        如果没有票了，那么就返回False
        :return:
        """
        self.wait_until_appear(RealmRaidAssets.I_BACK_RED)
        self.screenshot()
        cu, res, total = self.O_NUMBER.ocr(self.device.image)
        logger.info(f"cu = {cu}, res = {res}, total = {total}")
        if cu == 0 and cu + res == total:
            logger.warning(f'Execute round failed, no chance to attack')
            return False
        return True

    def medal_fire(self):
        """
        点击勋章
        :return:
        """
        # 点击勋章的挑战 和挑战
        time.sleep(0.2)
        is_click = False
        while 1:
            self.screenshot()
            if self.appear(RealmRaidAssets.I_FIRE, threshold=0.8):
                break

            if self.appear_then_click(RealmRaidAssets.I_SOUL_RAID, interval=1.5):
                while 1:
                    self.screenshot()
                    if self.appear_then_click(RealmRaidAssets.I_SOUL_RAID, interval=1.5):
                        continue
                    if not self.appear(RealmRaidAssets.I_SOUL_RAID, threshold=0.6):
                        break
                continue

            target = self.medal_grid.find_anyone(self.device.image)
            if target:
                self.appear_then_click(target, interval=2)  # 点击勋章,但是设置为两秒的间隔，适应不同的模拟器速度
                is_click = not is_click

            if is_click:
                continue
        logger.info(f'Click Medal')

        # 点击挑战
        self.wait_until_appear(RealmRaidAssets.I_FIRE)
        while 1:
            self.screenshot()
            if self.appear_then_click(RealmRaidAssets.I_FIRE, interval=2):
                continue
            if not self.appear(RealmRaidAssets.I_FIRE, threshold=0.8):
                break
        logger.info(f'Click {RealmRaidAssets.I_FIRE.name}')

    def execute_round(self) -> bool:
        """
        执行一轮 除非票不够，一直到到九次
        :return:
        """
        ryou_config = self.config.ryou_toppa
        # 如果没有票了，就退出
        if not self.is_ticket():
            return False
        if not self.is_target_available():
            return False


        # 打20次
        for i in range(30):
            if not self.is_ticket():
                return False
            if not self.is_target_available():
                return False
            self.medal_fire()
            self.run_general_battle(ryou_config.general_battle_config)
            self.wait_until_appear(RealmRaidAssets.I_BACK_RED)

        return True

    # 判断是否还有可进攻的目标
    def is_target_available(self) -> bool:
        """
            如果没有可进攻目标了，那么就返回False
            :return:
            """
        self.wait_until_appear(RealmRaidAssets.I_BACK_RED)
        self.screenshot()
        # 有徽章被检测到
        if self.medal_grid.find_anyone(self.device.image):
            return True
        # 没有徽章被检测到，且目标寮已被攻破
        elif self.appear(self.I_SUCCESS_PENETRATION, threshold=0.8):
            logger.info(f'Execute round failed, no target')
            return False
        else:
            raise GamePageUnknownError


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas1')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()
