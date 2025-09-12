# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import random
from datetime import datetime, timedelta, time
from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.AreaBoss.assets import AreaBossAssets
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.BaseActivity.config_activity import ApMode
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.GameUi.game_ui import GameUi

from module.logger import logger
from module.exception import TaskEnd
from module.base.protect import random_sleep

import cv2
import numpy as np
from module.atom.ocr import RuleOcr

class ScriptTask(GameUi, BaseActivity, SwitchSoul, ActivityShikigamiAssets):

    def run(self) -> None:

        config = self.config.activity_shikigami
        self.limit_time: timedelta = config.general_climb.limit_time
        if isinstance(self.limit_time, time):
            self.limit_time = timedelta(hours=self.limit_time.hour, minutes=self.limit_time.minute,
                                        seconds=self.limit_time.second)
        self.limit_count = config.general_climb.limit_count

        if config.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(config.switch_soul_config.switch_group_team)
        if config.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(
                config.switch_soul_config.group_name,
                config.switch_soul_config.team_name
            )

        self.ui_get_current_page()
        self.ui_goto(page_main)

        # 某些活动需要开启御魂加成
        # self.open_buff()
        # self.soul(is_open=True)
        # self.close_buff()

        self.home_main()

        # 选择是游戏的体力还是活动的体力
        current_ap = config.general_climb.ap_mode
        self.switch(current_ap)

        # 设定是否锁定阵容

        if config.general_battle.lock_team_enable:
            logger.info("Lock team")
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_UNLOCK, interval=1):
                    continue
                if self.appear(self.I_LOCK):
                    break
        else:
            logger.info("Unlock team")
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_LOCK, interval=1):
                    continue
                if self.appear(self.I_UNLOCK):
                    break

        # 流程应该是 在页面处：
        # 1. 判定计数是否超了，时间是否超了
        # 2. 如果是消耗活动体力，判定活动体力是否足够 如果是消耗一般的体力，判定一般体力是否足够
        # 3. 如果开启买体力，就买体力
        # 4. 如果开启了切换到游戏体力，就切换
        while 1:
            # 1
            if self.limit_time is not None and self.limit_time + self.start_time < datetime.now():
                logger.info("Time out")
                break
            if self.current_count >= self.limit_count:
                logger.info("Count out")
                break
            # 2
            self.wait_until_appear(self.I_FIRE)
            is_remain = self.check_ap_remain(current_ap)
            # 如果没有剩余了且这个时候是体力，就退出活动
            if not is_remain and current_ap == ApMode.AP_GAME:
                logger.info("Game ap out")
                break
            # 如果不是那就切换到体力
            elif not is_remain and current_ap == ApMode.AP_ACTIVITY:
                if config.general_climb.activity_toggle:
                    logger.info("Activity ap out and switch to game ap")
                    current_ap = ApMode.AP_GAME
                    self.switch(current_ap)
                    continue
                else:
                    logger.info("Activity ap out")
                    break

            # 随机休息
            if config.general_climb.random_sleep:
                random_sleep(probability=0.2)
            # 点击战斗
            logger.info("Click battle")
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_FIRE, interval=2):
                    continue
                if not self.appear(self.I_FIRE):
                    break
                if self.appear_then_click(self.I_C_CONFIRM1, interval=0.6):
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                    continue
                if self.appear_then_click(self.I_N_CONFIRM, interval=1):
                    continue

            if self.run_general_battle(config=config.general_battle):
                logger.info("General battle success")

        self.main_home()
        # 某些活动需要开启御魂加成
        # self.open_buff()
        # self.soul(is_open=False)
        # self.close_buff()
        if config.general_climb.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def home_main(self) -> bool:
        """
        从庭院到活动的爬塔界面，统一入口
        :return:
        """

        logger.hr("Enter Shikigami", 2)
        while 1:
            self.screenshot()
            self.C_RANDOM_LEFT.name = "BATTLE_RANDOM"
            self.C_RANDOM_RIGHT.name = "BATTLE_RANDOM"
            self.C_RANDOM_TOP.name = "BATTLE_RANDOM"
            self.C_RANDOM_BOTTOM.name = "BATTLE_RANDOM"
            if self.appear(self.I_FIRE):
                break
            if self.appear(self.I_SHI):
                # 有时会点到小纸人其他活动入口，等待稳定
                self.wait_until_stable(self.I_SHI)
                self.click(self.I_SHI, interval=1)
                continue
            if self.ocr_appear_click(self.O_ENTRY_ACTIVITY, interval=1):
                continue
            if self.appear_then_click(self.I_TOGGLE_BUTTON, interval=3):
                continue
            if self.appear_then_click(self.I_SKIP_BUTTON, interval=1.5):
                continue
            # 如果出现了 “获得奖励”
            reward_click = random.choice([self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM])
            if self.appear_then_click(self.I_UI_REWARD, action=reward_click, interval=1.3):
                continue
            if self.appear_then_click(self.I_RED_EXIT, interval=1.5):
                continue
            if self.appear_then_click(self.I_BATTLE, interval=2):
                continue

    def main_home(self) -> bool:
        """
        从活动的爬塔界面到庭院
        :return:
        """
        logger.hr("Exit Shikigami", 2)
        while 1:
            self.screenshot()
            if self.appear(self.I_SHI):
                break
            if self.appear_then_click(self.I_UI_BACK_RED, interval=2):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=2):
                continue
            if self.appear_then_click(self.I_BACK_GREEN, interval=2):
                continue
            if self.appear_then_click(self.I_EXIT, interval=2.2, threshold=0.6):
                continue

    def check_ap_remain(self, current_ap: ApMode) -> bool:
        """
        检查体力是否足够
        :return: 如何还有体力，返回True，否则返回False
        """
        self.screenshot()
        if current_ap == ApMode.AP_ACTIVITY:
            res: int = self.O_REMAIN_AP_ACTIVITY2.ocr_digit(
                self._prepare_image_for_ocr(self.device.image, asset=self.O_REMAIN_AP_ACTIVITY2))
            if res <= 0:
                logger.warning(f'Activity ap {res} not enough')
                return False
            return True
            # cu, res, total = self.O_REMAIN_AP_ACTIVITY.ocr(image=self.device.image)
            # if cu == 0 and cu + res == total:
            #     logger.warning("Activity ap not enough")
            #     return False
            # return True

        elif current_ap == ApMode.AP_GAME:
            cu: int = self.O_REMAIN_AP.ocr_digit(self._prepare_image_for_ocr(self.device.image,asset=self.O_REMAIN_AP))
            if cu > 0:
                logger.warning(f'Game ap {cu} more than 0')
                return True
            logger.warning(f'Game ap not enough: {cu}')
            return False

            # cu, res, total = self.O_REMAIN_AP.ocr(image=self.device.image)
            # if cu == total and cu + res == total:
            #     if cu > total:
            #         logger.warning(f'Game ap {cu} more than total {total}')
            #         return True
            #     logger.warning(f'Game ap not enough: {cu}')
            #     return False
            #
            # return True

    def switch(self, current_ap: ApMode) -> None:
        """
        切换体力
        :param current_ap:
        :return:
        """
        if current_ap == ApMode.AP_ACTIVITY:
            logger.info("Select activity ap")
            while 1:
                self.screenshot()
                if self.appear(self.I_AP_ACTIVITY):
                    break
                if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                    continue
                if self.appear(self.I_AP, interval=1):
                    self.appear_then_click(self.I_SWITCH, interval=2)  # 点击切换
        else:
            logger.info("Select game ap")
            while 1:
                self.screenshot()
                if self.appear(self.I_AP):
                    break
                if self.appear(self.I_AP_ACTIVITY, interval=1):
                    self.appear_then_click(self.I_SWITCH, interval=2)

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 重写，不出现达摩版本999专用
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info("Start battle process")
        self.C_RANDOM_LEFT.name = "BATTLE_RANDOM"
        self.C_RANDOM_RIGHT.name = "BATTLE_RANDOM"
        self.C_RANDOM_TOP.name = "BATTLE_RANDOM"
        self.C_RANDOM_BOTTOM.name = "BATTLE_RANDOM"
        click_count = 0
        while 1:
            self.screenshot()
            # 如果出现了 “获得奖励”
            reward_click = random.choice([self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM])
            if self.appear_then_click(self.I_UI_REWARD, action=reward_click, interval=1.3):
                click_count += 1
                continue
            # 如果出现了 “鼓”
            if self.appear(self.I_WIN) or click_count >= 1:
                logger.info("Win")
                while 1:
                    self.screenshot()
                    if not self.appear(self.I_WIN):
                        break
                    if self.appear_then_click(self.I_WIN, action=self.C_RANDOM_ALL, interval=1.1):
                        continue
                if self.appear(self.I_FIRE):
                    return True
            # 失败 -> 正常人不会失败
            if self.appear(self.I_FALSE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False
            # 如果开启战斗过程随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()

    def _prepare_image_for_ocr(self, image: np.ndarray, asset: RuleOcr) -> np.ndarray:

        image_copy = image.copy()
        x, y, w, h = asset.roi

        roi_to_process = image_copy[y:y + h, x:x + w]
        if len(roi_to_process.shape) == 3:
            gray_image = cv2.cvtColor(roi_to_process, cv2.COLOR_BGR2GRAY)
        else:
            gray_image = roi_to_process

        # 自适应二值化
        _, binary_norm = cv2.threshold(gray_image, 127, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        _, binary_inv = cv2.threshold(gray_image, 127, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

        if cv2.countNonZero(binary_norm) < cv2.countNonZero(binary_inv):
            binary_correct = binary_norm
        else:
            binary_correct = binary_inv

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
        dilated_image = cv2.dilate(binary_correct, kernel, iterations=1)

        # 找轮廓
        contours, _ = cv2.findContours(dilated_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        processed_roi_content = None
        if contours:
            all_points = np.concatenate(contours, axis=0)
            bx, by, bw, bh = cv2.boundingRect(all_points)

            processed_roi_content = binary_correct[by:by + bh, bx:bx + bw]

        centered_roi = np.full((h, w), 255, dtype=np.uint8)  # 255代表白色

        if processed_roi_content is not None:
            content_h, content_w = processed_roi_content.shape

            if content_h <= h and content_w <= w:
                # 计算居中粘贴的位置，放到中间
                start_y = (h - content_h) // 2
                start_x = (w - content_w) // 2

                paste_area = centered_roi[start_y:start_y + content_h, start_x:start_x + content_w]

                paste_area[processed_roi_content == 255] = 0
            else:
                logger.warning(f"Content for asset '{asset.name}' is larger than ROI. Skipping centering.")
                # 内容过大，直接使用原始二值图的反转作为结果
                centered_roi = cv2.bitwise_not(binary_correct)
        else:
            logger.warning(f"No content found in ROI for asset: {asset.name}. ROI will be blank.")

        processed_roi_bgr = cv2.cvtColor(centered_roi, cv2.COLOR_GRAY2BGR)
        image_copy[y:y + h, x:x + w] = processed_roi_bgr

        return image_copy



    """
    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 重写，出现达摩版本月度常用
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info("Start battle process")
        self.C_RANDOM_LEFT.name = "BATTLE_RANDOM"
        self.C_RANDOM_RIGHT.name = "BATTLE_RANDOM"
        self.C_RANDOM_TOP.name = "BATTLE_RANDOM"
        self.C_RANDOM_BOTTOM.name = "BATTLE_RANDOM"
        click_count = 0
        while 1:
            self.screenshot()
            # 如果出现了 “鼓”
            if self.appear_then_click(self.I_WIN, interval=2.3):
                logger.info("Win")
                continue
            #  出现 “魂” 和 紫蛇皮
            if self.appear(self.I_REWARD):
                logger.info('Win battle')
                self.wait_until_appear(self.I_REWARD_PURPLE_SNAKE_SKIN, wait_time=5)
                while 1:
                    self.screenshot()
                    appear_reward = self.appear(self.I_REWARD)
                    appear_reward_purple_snake_skin = self.appear(self.I_REWARD_PURPLE_SNAKE_SKIN)
                    if not appear_reward and not appear_reward_purple_snake_skin and click_count >= 1:
                        break
                    if appear_reward or appear_reward_purple_snake_skin:
                        reward_click = random.choice(
                            [self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP])
                        self.click(reward_click, interval=1.8)
                        click_count += 1
                        continue
                return True

            # 失败 -> 正常人不会失败
            if self.appear(self.I_FALSE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False
            # 如果开启战斗过程随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()
    """


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
