# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep

import cv2
import numpy as np
import random
import tasks.Component.GeneralBattle.config_general_battle
from datetime import datetime, timedelta, time
from module.atom.ocr import RuleOcr
from module.base.protect import random_sleep
from module.exception import TaskEnd
from module.logger import logger
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.config import SwitchSoulConfig, GeneralBattleConfig
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.BaseActivity.config_activity import GeneralClimb
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records, page_climb_act, page_climb_act_pass, \
    page_climb_act_boss, page_climb_act_ap, Page, page_climb_act_buff


def get_run_order_list(climb_conf: GeneralClimb) -> list[str]:
    if not climb_conf.run_sequence or len(climb_conf.run_sequence.split(',')) == 1:
        raise ValueError('Run sequence now is empty, must set it')
    run_order_list = [climb_type.strip() for climb_type in climb_conf.run_sequence.split(',')]
    return [climb_type for climb_type in run_order_list if getattr(climb_conf, f'enable_{climb_type}')]


def _prepare_image_for_ocr(image: np.ndarray, asset: RuleOcr) -> np.ndarray:

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


class ScriptTask(GameUi, BaseActivity, SwitchSoul, ActivityShikigamiAssets):
    # key: climb type value: run count
    count_map: dict[str, int] = {
        'pass': 0,
        'ap': 0,
        'boss': 0
    }
    page_map: dict[str, Page] = {
        'pass': page_climb_act_pass,
        'ap': page_climb_act_ap,
        'boss': page_climb_act_boss,
    }

    climb_type: str = 'pass'
    run_idx: int = 0

    def run(self) -> None:
        config = self.config.activity_shikigami
        self.limit_time: timedelta = config.general_climb.limit_time
        if isinstance(self.limit_time, time):
            self.limit_time = timedelta(hours=self.limit_time.hour, minutes=self.limit_time.minute,
                                        seconds=self.limit_time.second)
        # 初始化爬塔类型
        self.climb_type = get_run_order_list(config.general_climb)[0]
        while 1:
            # 切换御魂
            self.switch_soul(config.switch_soul_config)
            # 进入爬塔活动主界面
            self.home_main()
            # 切换buff
            self.switch_buff(config.general_climb)
            # 锁定阵容
            self.lock_team(config.general_battle)
            while 1:
                switch = False
                # 超时退出
                if self.limit_time is not None and datetime.now() - self.start_time >= self.limit_time:
                    logger.info(f"{self.climb_type} time out")
                    break
                # 次数达到限制切换下一种爬塔
                if self.get_count() >= self.get_limit(config.general_climb):
                    logger.warn(f"{self.climb_type} count out, switch to next")
                    switch = self.switch_next()
                    break
                # 判断是否可以运行
                can_run = self.check_can_run()
                if not can_run:
                    logger.warn(f'{self.climb_type} tickets not enough, switch to next')
                    switch = self.switch_next()
                    break
                # 开始战斗
                self.start_battle()
            if not switch:
                break
        # 返回庭院
        self.main_home()
        if config.general_climb.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def switch_soul(self, conf: SwitchSoulConfig):
        """
        根据当前爬塔类型自动切换御魂
        :param conf: 切换御魂配置
        :return:
        """
        enable_switch = getattr(conf, f"enable_switch_{self.climb_type}", False)
        enable_by_name = getattr(conf, f"enable_switch_{self.climb_type}_by_name", False)
        if enable_switch or enable_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
        if enable_by_name:
            group_name = getattr(conf, f"{self.climb_type}_group_team_name", '-1,-1')
            if not group_name or len(group_name.split(',')) != 2:
                raise ValueError('switch soul by name must be 2 length')
            group, team = group_name.split(",")
            self.run_switch_soul_by_name(group, team)
        elif enable_switch:
            group_team = getattr(conf, f"{self.climb_type}_group_team", '-1,-1')
            self.run_switch_soul(group_team)

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """
        根据配置判断当前爬塔类型是否锁定阵容, 并执行锁定或解锁
        :param battle_conf: 战斗配置
        :return:
        """
        self.ui_get_current_page()
        self.ui_goto(self.page_map[self.climb_type])
        enable_preset = getattr(battle_conf, f"enable_{self.climb_type}_preset", False)
        if not enable_preset:
            logger.info(f'Lock {self.climb_type} team')
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_UNLOCK, interval=1):
                    continue
                if self.appear(self.I_LOCK):
                    return
        logger.info(f'Unlock {self.climb_type} team')
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_LOCK, interval=1):
                continue
            if self.appear(self.I_UNLOCK):
                break

    def switch_buff(self, climb_conf: GeneralClimb):
        buffs = getattr(climb_conf, f'{self.climb_type}_buff', None)
        if not buffs or len(buffs.split(',')) == 1:
            logger.info('Not set buff, skip')
            return
        buff_list = [buff.strip() for buff in buffs.split(',')]
        if not buff_list:
            logger.info('Buff incorrect formatting, skip')
            return
        self.ui_get_current_page()
        self.ui_goto(page_climb_act_buff)
        buff_box_list = [self.C_BUFF_1_BOX, self.C_BUFF_2_BOX]
        buff_box_empty_list = [self.I_BUFF_BOX_1_EMPTY, self.I_BUFF_BOX_2_EMPTY]
        buff_up_map = {
            'buff_1': self.C_BUFF_1_UP,
            'buff_2': self.C_BUFF_2_UP,
            'buff_3': self.C_BUFF_3_UP,
            'buff_4': self.C_BUFF_4_UP,
            'buff_5': self.C_BUFF_5_UP
        }
        logger.info(f'start switch {self.climb_type} {buff_list}')
        for i, buff_box in enumerate(buff_box_list):
            logger.info(f'Start down {buff_list[i]}')
            ok = 0
            while ok <= 3:
                self.screenshot()
                # 打开buff面板
                self.click(buff_box, interval=1.5)
                ok = (ok + 1) if self.appear(buff_box_empty_list[i]) else 0
                # 卸下buff
                self.appear_then_click(self.I_BUFF_DOWN, interval=0.5)
            logger.info(f'Down {buff_list[i]} ok')
        for i, buff_box in enumerate(buff_box_list):
            logger.info(f'Start up {buff_list[i]}')
            ok = 0
            while ok <= 3:
                self.screenshot()
                # 打开buff面板
                self.click(buff_box, interval=1.5)
                ok = (ok + 1) if not self.appear(buff_box_empty_list[i]) else 0
                # 装上buff
                self.appear_then_click(self.I_BUFF_UP, buff_up_map[buff_list[i]], interval=0.5)
            logger.info(f'Up {buff_list[i]} ok')

    def get_count(self) -> int:
        """
        获取当前爬塔类型运行次数
        :return: 运行次数
        """
        return self.count_map[self.climb_type]

    def check_can_run(self) -> bool:
        """
        判断当前爬塔类型能否运行
        pass: 剩余门票爬塔票数>0
        ap: 剩余体力爬塔票数>0
        boss: 剩余挑战次数>0
        :return: True 可以运行 or False
        """
        self.ui_get_current_page()
        self.ui_goto(self.page_map[self.climb_type])
        logger.info(f'Check the {self.climb_type} can work')
        self.wait_until_appear(self.I_FIRE)
        self.screenshot()
        remain_times = 0
        if self.climb_type == 'pass':
            remain_times = self.O_REMAIN_AP_ACTIVITY2.ocr_digit(
                _prepare_image_for_ocr(self.device.image, asset=self.O_REMAIN_AP_ACTIVITY2))
        if self.climb_type == 'ap':
            remain_times = self.O_REMAIN_AP.ocr_digit(
                _prepare_image_for_ocr(self.device.image, asset=self.O_REMAIN_AP))
        if self.climb_type == 'boss':
            _, remain_times, _ = self.O_REMAIN_BOSS.ocr_digit_counter(self.device.image)
        return remain_times > 0

    def get_limit(self, climb_conf: GeneralClimb) -> int:
        """
        获取配置中当前爬塔类型次数限制
        :param climb_conf: 爬塔配置
        :return: 限制次数
        """
        limit = getattr(climb_conf, f'{self.climb_type}_limit', 0)
        return 0 if not limit else limit

    def switch_next(self) -> bool:
        """
        切换下一种爬塔类型
        :return: True 切换成功 or False
        """
        self.run_idx += 1
        climb_type_list = get_run_order_list(self.config.activity_shikigami.general_climb)
        if self.run_idx >= len(climb_type_list):
            logger.info('All tower climbing activities have been completed')
            return False
        self.climb_type = climb_type_list[self.run_idx]
        self.current_count = 0
        return True

    def start_battle(self):
        # 点击战斗前随机休息
        if self.config.activity_shikigami.general_climb.random_sleep:
            random_sleep(probability=0.2)
        logger.info("Click battle")
        while 1:
            self.screenshot()
            # 点击挑战
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
        # 运行战斗
        if self.run_general_battle(config=self.get_general_battle_conf()):
            self.count_map[self.climb_type] += 1
            logger.info("General battle success")

    def get_general_battle_conf(self) -> tasks.Component.GeneralBattle.config_general_battle.GeneralBattleConfig:
        from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig as gbc
        conf = self.config.activity_shikigami
        enable_preset = getattr(conf.general_battle, f'enable_{self.climb_type}_preset', False)
        group_team = getattr(conf.switch_soul_config, f'{self.climb_type}_group_team')
        if enable_preset and (not group_team or len(group_team.split(',')) != 2):
            raise ValueError('Enable preset but group team not set correct!')
        group, team = group_team.split(',')
        return gbc(lock_team_enable=not enable_preset,
                   preset_enable=enable_preset,
                   preset_group=group if enable_preset else 1,
                   preset_team=team if enable_preset else 1,
                   green_enable=getattr(conf.general_battle, f'enable_{self.climb_type}_green', False),
                   green_mark=getattr(conf.general_battle, f'{self.climb_type}_green_mark'),
                   random_click_swipt_enable=getattr(conf.general_battle, f'enable_{self.climb_type}_anti_detect', False), )

    def home_main(self) -> bool:
        """
        从庭院到活动的爬塔界面，(只到爬塔活动主界面)
        :return:
        """
        logger.hr("Enter Shikigami", 2)
        self.ui_get_current_page()
        self.main_goto_act_by_list(page_climb_act)

    def main_home(self) -> bool:
        """
        从活动的爬塔界面到庭院
        :return:
        """
        logger.hr("Exit Shikigami", 2)
        self.ui_get_current_page()
        self.ui_goto(page_main)

    def random_reward_click(self, exclude_bottom=False):
        options = [self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP]
        if not exclude_bottom:
            options.append(self.C_RANDOM_BOTTOM)
        target = random.choice(options)
        self.click(target, interval=1.8)
        return 1

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 通用战斗结束判断
        self.device.stuck_record_add("BATTLE_STATUS_S")
        self.device.click_record_clear()
        logger.info("Start battle process")

        for btn in (self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM):
            btn.name = "BATTLE_RANDOM"
        ok_cnt, max_retry = 0, 5
        while 1:
            self.screenshot()
            sleep(0.5)
            # 已经回到对应挑战界面
            if self.ui_page_appear(self.page_map[self.climb_type]):
                break
            # 达到最大重试次数且没有回到活动界面
            if ok_cnt > max_retry:
                self.click(self.random_reward_click(exclude_bottom=True), interval=1)
                break
            # 已经胜利但是后续识别失败则重新识别并点击
            if 0 < ok_cnt <= max_retry:
                # 紫蛇皮消失
                self.ui_click_until_smt_disappear(self.random_reward_click(exclude_bottom=True),
                                                  self.I_REWARD_PURPLE_SNAKE_SKIN, interval=1.6)
                self.ui_get_current_page()
                self.ui_goto(self.page_map[self.climb_type])
                ok_cnt += 1
                continue
            # 胜利(鼓 | 魂 | 获得奖励)
            if self.appear(self.I_WIN) or self.appear(self.I_REWARD) or self.appear(self.I_UI_REWARD):
                if ok_cnt == 0:
                    logger.info("Win battle")
                # 鼓消失
                self.ui_click_until_smt_disappear(self.random_reward_click(), self.I_WIN, interval=1.1)
                # 魂消失
                self.ui_click_until_smt_disappear(self.random_reward_click(exclude_bottom=True), self.I_REWARD,
                                                  interval=1.3)
                # 紫蛇皮消失
                self.ui_click_until_smt_disappear(self.random_reward_click(exclude_bottom=True),
                                                  self.I_REWARD_PURPLE_SNAKE_SKIN, interval=1.6)
                # 获得奖励消失
                self.ui_click_until_smt_disappear(self.random_reward_click(),
                                                  self.I_UI_REWARD, interval=1.6)
                ok_cnt += 1
                continue
            # 失败
            if self.appear(self.I_FALSE):
                logger.warning("False battle")
                self.ui_click_until_smt_disappear(self.random_reward_click(), self.I_FALSE, interval=1.5)
                return False
            # 战斗中随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()
        return True


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas3')
    d = Device(c)
    t = ScriptTask(c, d)

    t.switch_buff(c.activity_shikigami.general_climb)
