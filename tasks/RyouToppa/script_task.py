# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from tasks.RyouToppa.assets import RyouToppaAssets
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_realm_raid, page_main, page_ryou_toppa
from tasks.RealmRaid.assets import RealmRaidAssets
from module.logger import logger
from module.exception import TaskEnd
from module.atom.image_grid import ImageGrid


class ScriptTask(GeneralBattle, GameUi, RyouToppaAssets):
    medal_grid: ImageGrid = None

    def run(self):
        """
        执行
        :return:
        """
        config = self.config.ryou_toppa
        self.medal_grid = ImageGrid([RealmRaidAssets.I_MEDAL_5, RealmRaidAssets.I_MEDAL_4, RealmRaidAssets.I_MEDAL_3,
                                     RealmRaidAssets.I_MEDAL_2, RealmRaidAssets.I_MEDAL_1, RealmRaidAssets.I_MEDAL_0])
        self.ui_get_current_page()
        self.ui_goto(page_realm_raid)

        # 点击突破
        while 1:
            self.screenshot()
            if self.appear_then_click(RealmRaidAssets.I_REALM_RAID, interval=1):
                continue
            if self.appear(RealmRaidAssets.I_BACK_RED, threshold=0.6):
                break
        logger.info(f'Click {RealmRaidAssets.I_REALM_RAID.name}')

        ryou_toppa_start_flag = True

        # 点击寮突
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_RYOU_TOPPA, interval=1):
                continue
            # 出现选择寮突说明寮突未开
            if self.appear(self.I_SELECT_RYOU_BUTTON, threshold=0.8):
                ryou_toppa_start_flag = False
                break
            # 出现寮奖励， 说明寮突已开
            if self.appear(self.I_RYOU_REWARD, threshold=0.8):
                ryou_toppa_start_flag = True
                break
            # 攻破阴阳寮，说明寮突已开，则退出
            if self.appear(self.I_SUCCESS_PENETRATION, threshold=0.8):
                ryou_toppa_start_flag = True
                break
        logger.info(f'Click {self.I_RYOU_TOPPA.name}')

        # 寮突未开 并且有权限， 开开寮突
        if not ryou_toppa_start_flag and config.raid_config.ryou_access == 'yes':
            # 开寮突
            self.start_ryou_toppa()

        # 切换阵容 再说

        # 开始突破
        while 1:
            # 攻破阴阳寮，则退出
            if self.appear(self.I_SUCCESS_PENETRATION, threshold=0.8):
                break
            # 点击结界， 并挑战
            self.medal_fire()
            self.run_general_battle(config.general_battle_config)
            self.wait_until_appear(RealmRaidAssets.I_BACK_RED)

        # 回 page_main 失败
        # self.ui_current = page_ryou_toppa
        # self.ui_goto(page_main)

        self.set_next_run(task='RyouToppa', success=True)
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
                continue
            # 出现勋章奖励标题,说明已进入，则退出
            if self.appear(self.I_GUILD_ORDERS_REWARDS, threshold=0.8):
                break
        logger.info(f'Click {self.I_SELECT_RYOU_BUTTON.name}')

        # 选择第一个寮
        while 1:
            self.screenshot()
            if self.appear(self.I_RYOU_TOPPA, interval=1):
                self.click(self.C_SELECT_FIRST_RYOU)
                continue
            # 出现突入开始，则退出
            if self.appear(self.I_START_TOPPA_BUTTON, threshold=0.8):
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

    def medal_fire(self) -> bool:
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