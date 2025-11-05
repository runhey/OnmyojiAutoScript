# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum, auto
from time import sleep

import cv2
import numpy as np
import random
import tasks.Component.GeneralBattle.config_general_battle
from datetime import datetime, timedelta, time
from module.atom.click import RuleClick
from module.atom.ocr import RuleOcr
from module.base.protect import random_sleep
from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.config import SwitchSoulConfig, GeneralBattleConfig, ActivityShikigami
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.BaseActivity.config_activity import GeneralClimb
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
import tasks.ActivityShikigami.page as game
from typing import Any


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


class Status(Enum):
    TIME_OUT = auto()  # 超时
    DOWN = auto()  # 当前爬塔类型完成
    ALL_DOWN = auto()  # 所有爬塔类型完成
    ALREADY_SWITCH_SOUL = auto()  # 已经切换御魂
    ALREADY_LOCK_TEAM = auto()  # 已经锁定队伍
    ALREADY_SWITCH_BUFF = auto()  # 已经切换buff
    GOTO_ACT_FAILED = auto()  # 前往活动失败
    ENTER_BATTLE_FAILED = auto()  # 进入战斗失败
    COUNT_LIMIT = auto()  # 达到次数限制
    NO_TICKETS = auto()  # 没有票数


class ScriptTask(GameUi, BaseActivity, SwitchSoul, ActivityShikigamiAssets):
    _check_map = None
    _count_map = None

    page_map: dict[str, game.Page] = {
        'pass': game.page_climb_act_pass,
        'ap': game.page_climb_act_ap,
        'boss': game.page_climb_act_boss,
        'ap100': game.page_climb_act_ap100,
    }
    run_idx: int = 0
    conf: ActivityShikigami = None

    def run(self) -> None:
        self.conf = self.config.activity_shikigami
        self.limit_time: timedelta = self.conf.general_climb.limit_time_v
        while True:
            self.put_status()
            # 超时或全部完成则退出
            if self.check(Status.TIME_OUT) or self.check(Status.ALL_DOWN):
                logger.hr(f'Climb act all down')
                break
            # 当前爬塔类型完成了或达到次数限制了, 切换下一个类型
            if self.check(Status.DOWN) or self.check(Status.COUNT_LIMIT):
                self.switch_next()
                continue
            # 获取当前页面
            current_page = self.ui_get_current_page(False)
            match current_page:
                # 庭院, 进入活动主界面
                case game.page_main:
                    self.switch_soul(self.conf.switch_soul_config)
                    self.home_main()
                # 活动主界面或副界面, 进入最终爬塔界面
                case game.page_climb_act | game.page_climb_act_2:
                    self.switch_soul(self.conf.switch_soul_config)
                    # self.ui_goto(game.page_climb_act_buff)
                    self.goto_act()
                # buff界面, 进入最终爬塔界面
                case game.page_climb_act_buff:
                    self.switch_buff(self.conf.general_climb)
                    self.goto_act()
                # 最终爬塔界面
                case game.page_climb_act_pass | game.page_climb_act_ap | game.page_climb_act_ap100 | game.page_climb_act_boss:
                    self.switch_soul(self.conf.switch_soul_config)
                    self.lock_team(self.conf.general_battle)
                    self.check_tickets_enough()
                    self.start_battle()
                case game.page_battle:
                    self.battle_wait(getattr(self.conf.general_battle, f'enable_{self.climb_type}_anti_detect', False))
                case _:
                    if self.check(Status.GOTO_ACT_FAILED):
                        logger.warning(f'Climb type[{self.climb_type}] goto failed')
                        self.put_check(Status.DOWN, True)
                        continue
                    self.put_check(Status.GOTO_ACT_FAILED, True)
                    # 任何活动界面都没有识别到, 尝试主动前往爬塔活动
                    self.goto_act(timeout=25)
        # 返回庭院
        self.main_home()
        if self.conf.general_climb.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def start_battle(self):
        # 先识别是否在挑战界面, 不在则交给上层处理
        if not self.wait_until_appear(self.O_FIRE, wait_time=3):
            logger.warning(f'Detect fire fail, try reidentify')
            return
        # 点击战斗前随机休息
        if self.conf.general_climb.random_sleep:
            random_sleep(probability=0.2)
        click_times, max_times = 0, random.randint(2, 4)
        while 1:
            self.screenshot()
            if self.is_in_battle(False):
                # 进入战斗了则一定有门票
                self.put_check(Status.NO_TICKETS, False)
                break
            if click_times >= max_times:
                # 挑战点击失败, 且无门票则大概率真没有票了
                if self.check(Status.NO_TICKETS):
                    self.put_check(Status.DOWN, True)
                    logger.info(f'Climb {self.climb_type} no tickets detected, try next')
                    return
                # 有门票且挑战已经点击失败过一次了
                if self.check(Status.ENTER_BATTLE_FAILED):
                    logger.warning(f'Climb {self.climb_type} cannot enter, maybe already end, try next')
                    self.put_check(Status.DOWN, True)
                    return
                # 有门票但挑战点击失败, 交给上层处理
                logger.warning(f'Climb type {self.climb_type} enter fail, try reidentify')
                self.put_check(Status.ENTER_BATTLE_FAILED, True)
                return
            # 点击挑战
            if self.ocr_appear_click(self.O_FIRE, interval=2):
                click_times += 1
                logger.info(f'Try click fire, remain times[{max_times - click_times}]')
                continue
            if ((self.appear_then_click(self.I_C_CONFIRM1, interval=0.6) or
                 self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1) or
                 self.appear_then_click(self.I_UI_CONFIRM, interval=1)) or
                    self.appear_then_click(self.I_N_CONFIRM, interval=1)):
                continue
        # 运行战斗
        self.run_general_battle(config=self.get_general_battle_conf())

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 通用战斗结束判断
        self.device.stuck_record_add("BATTLE_STATUS_S")
        self.device.click_record_clear()
        logger.info(f"Start {self.climb_type} battle process")
        self.count_map[self.climb_type] = self.current_count
        for btn in (self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM):
            btn.name = "BATTLE_RANDOM"
        ok_cnt, max_retry = 0, 5
        single_start_time = datetime.now()
        while 1:
            sleep(random.uniform(1, 1.5))
            self.screenshot()
            # 达到最大重试次数则直接交给上层处理
            if ok_cnt > max_retry:
                break
            # 识别到挑战说明已经退出战斗
            if ok_cnt > 0 and self.ocr_appear(self.O_FIRE):
                return True
            # 失败
            if self.appear(self.I_FALSE):
                logger.warning("Battle failed")
                self.ui_click_until_smt_disappear(self.random_reward_click(click_now=False), self.I_FALSE, interval=1.5)
                return False
            # 奖励界面
            if self.ui_page_appear(game.page_reward, interval=0.6):
                logger.info(f'Battle success, try close reward page[{ok_cnt}]')
                self.random_reward_click(exclude_click=[self.C_RANDOM_BOTTOM])
                ok_cnt += 1
                continue
            # 已经不在战斗中了, 且奖励也识别过了, 则随机点击
            if ok_cnt > 0 and not self.is_in_battle(False):
                self.random_reward_click(exclude_click=[self.C_RANDOM_BOTTOM])
                ok_cnt += 1
                continue
            # 单局到时间自动退出战斗
            if ok_cnt == 0 and datetime.now() - single_start_time > self.conf.general_climb.get_single_limit_time(
                    self.climb_type, timedelta(days=1)):
                logger.attr(self.climb_type, 'Time limit arrived, close current battle')
                self.exit_battle(skip_first=True)
                ok_cnt += 1
                continue
            # 战斗中随机滑动
            if ok_cnt == 0 and random_click_swipt_enable:
                self.random_click_swipt()
        return True

    def exit_battle(self, skip_first: bool = False) -> bool:
        """
        在战斗的时候强制退出战斗
        :param skip_first: 是否跳过第一次截屏
        :return: 退出战斗成功True or 失败False
        """
        timeout_timer = Timer(6).start()
        exit_clicked = False
        while not timeout_timer.reached():
            self.maybe_screenshot(skip_first)
            skip_first = False
            # 不在战斗界面, 认为退出成功
            if not self.is_in_battle(False):
                return True
            if exit_clicked:
                self.appear_then_click(self.I_EXIT_ENSURE)
            if not exit_clicked and self.appear_then_click(self.I_EXIT):
                exit_clicked = True
            sleep(random.uniform(0.5, 1.5))
        # 还在战斗界面且超时则退出失败
        return False

    def switch_soul(self, conf: SwitchSoulConfig):
        """
        根据当前爬塔类型自动切换御魂
        :param conf: 切换御魂配置
        :return:
        """
        if self.check(Status.ALREADY_SWITCH_SOUL):
            return
        conf.validate_switch_soul()
        self.put_check(Status.ALREADY_SWITCH_SOUL, True)
        enable_switch = getattr(conf, f"enable_switch_{self.climb_type}", False)
        enable_by_name = getattr(conf, f"enable_switch_{self.climb_type}_by_name", False)
        if enable_switch or enable_by_name:
            self.ui_goto(game.page_shikigami_records)
        if enable_by_name:
            group, team = getattr(conf, f"{self.climb_type}_group_team_name").split(",")
            self.run_switch_soul_by_name(group, team)
        elif enable_switch:
            group_team = getattr(conf, f"{self.climb_type}_group_team")
            self.run_switch_soul(group_team)
        self.goto_act()

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """
        根据配置判断当前爬塔类型是否锁定阵容, 并执行锁定或解锁
        :param battle_conf: 战斗配置
        :return:
        """
        if self.check(Status.ALREADY_LOCK_TEAM):
            return
        self.put_check(Status.ALREADY_LOCK_TEAM, True)
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
        if self.check(Status.ALREADY_SWITCH_BUFF):
            return
        self.put_check(Status.ALREADY_SWITCH_BUFF, True)
        buffs = getattr(climb_conf, f'{self.climb_type}_buff', None)
        if not buffs or len(buffs.split(',')) == 1:
            logger.info('Not set buff, skip')
            return
        buff_list = [buff.strip() for buff in buffs.split(',')]
        if not buff_list:
            logger.info('Buff incorrect formatting, skip')
            return
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

    def put_status(self):
        """
        更新全局状态
        """
        # 超过运行时间
        if self.limit_time is not None and datetime.now() - self.start_time >= self.limit_time:
            logger.warning(f"Climb type {self.climb_type} time out")
            self.put_check(Status.TIME_OUT, True)
        # 次数达到限制
        if self.get_count() >= self.get_limit():
            logger.info(f"Climb type {self.climb_type} count limit reached")
            self.put_check(Status.DOWN, True)

    def get_count(self) -> int:
        """
        获取当前爬塔类型运行次数
        :return: 运行次数
        """
        return self.count_map[self.climb_type]

    def check_tickets_enough(self):
        """
        判断当前爬塔门票是否足够
        :return: True 可以运行 or False
        """
        logger.hr(f'Check {self.climb_type} tickets')
        if not self.wait_until_appear(self.O_FIRE, wait_time=3):
            logger.warning(f'Detect fire fail, try reidentify')
            return
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
        if self.climb_type == 'ap100':
            remain_times = self.O_REMAIN_AP100.ocr_digit(
                _prepare_image_for_ocr(self.device.image, asset=self.O_REMAIN_AP100))
        self.put_check(Status.NO_TICKETS, remain_times <= 0)

    def get_limit(self) -> int:
        """
        获取配置中当前爬塔类型次数限制
        :return: 限制次数
        """
        limit = getattr(self.conf.general_climb, f'{self.climb_type}_limit', 0)
        return 0 if not limit else limit

    def switch_next(self):
        """
        切换下一种爬塔类型
        :return: True 切换成功 or False
        """
        self.run_idx += 1
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            logger.info('All climbing activities have been completed')
            self.put_check(Status.ALL_DOWN, True)
            return
        # 切换爬塔类型了, 恢复所有状态
        self.current_count = 0
        self.put_check(Status.ALREADY_SWITCH_SOUL, False)
        self.put_check(Status.ALREADY_LOCK_TEAM, False)
        self.put_check(Status.GOTO_ACT_FAILED, False)
        self.put_check(Status.ENTER_BATTLE_FAILED, False)
        self.put_check(Status.COUNT_LIMIT, False)
        logger.hr(f'Climb switch to {self.climb_type}', 2)

    def get_general_battle_conf(self) -> tasks.Component.GeneralBattle.config_general_battle.GeneralBattleConfig:
        from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig as gbc
        self.conf.validate_switch_preset()
        enable_preset = getattr(self.conf.general_battle, f'enable_{self.climb_type}_preset', False)
        group, team = getattr(self.conf.switch_soul_config, f'{self.climb_type}_group_team').split(',')
        return gbc(lock_team_enable=not enable_preset,
                   preset_enable=enable_preset,
                   preset_group=group if enable_preset else 1,
                   preset_team=team if enable_preset else 1,
                   green_enable=getattr(self.conf.general_battle, f'enable_{self.climb_type}_green', False),
                   green_mark=getattr(self.conf.general_battle, f'{self.climb_type}_green_mark'),
                   random_click_swipt_enable=getattr(self.conf.general_battle, f'enable_{self.climb_type}_anti_detect',
                                                     False), )

    def home_main(self) -> bool:
        """
        从庭院到活动的爬塔界面
        :return:
        """
        logger.hr("Enter Shikigami", 2)
        self.ui_goto(game.page_climb_act)

    def main_home(self) -> bool:
        """
        从活动的爬塔界面到庭院
        :return:
        """
        logger.hr("Exit Shikigami", 2)
        self.ui_get_current_page(False)
        self.ui_goto(game.page_main)

    def goto_act(self, timeout: int = 45):
        self.ui_goto(self.page_map[self.climb_type], timeout=timeout)

    def random_reward_click(self, exclude_click: list = None, click_now: bool = True) -> RuleClick:
        """
        随机点击
        :param exclude_click: 排除的点击位置
        :param click_now: 是否立即点击
        :return: 随机的点击位置
        """
        options = [self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM]
        if exclude_click:
            options = [option for option in options if option not in exclude_click]
        target = random.choice(options)
        if click_now:
            self.click(target, interval=1.8)
        return target

    @property
    def climb_type(self) -> str:
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            return self.conf.general_climb.run_sequence_v[-1]
        return self.conf.general_climb.run_sequence_v[self.run_idx]

    @property
    def count_map(self) -> dict[str, int]:
        """
        :return: key: climb type, value: run count
        """
        if not getattr(self, "_count_map", None):
            self._count_map = {climb_type: 0 for climb_type in self.conf.general_climb.run_sequence_v}
        return self._count_map

    @property
    def check_map(self) -> dict[str, dict[Status, Any]]:
        if not getattr(self, "_check_map", None):
            self._check_map = {
                climb_type: {status: None for status in list(Status)}
                for climb_type in self.conf.general_climb.run_sequence_v
            }
        return self._check_map

    def check(self, status: Status) -> Any:
        return self.check_map[self.climb_type][status]

    def put_check(self, status: Status, value: Any):
        self.check_map[self.climb_type][status] = value


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
