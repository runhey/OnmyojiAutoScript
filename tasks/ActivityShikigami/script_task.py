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
from module.exception import TaskEnd
from module.logger import logger
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.config import SwitchSoulConfig, GeneralBattleConfig
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.BaseActivity.config_activity import GeneralClimb
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
import tasks.GameUi.page as game
from typing import Any


def get_run_order_list(climb_conf: GeneralClimb) -> list[str]:
    if not climb_conf.run_sequence or len(climb_conf.run_sequence.split(',')) == 1:
        raise ValueError('Run sequence now is empty, must set it')
    run_order_list = [climb_type.strip() for climb_type in climb_conf.run_sequence.split(',')]
    return [climb_type for climb_type in run_order_list if getattr(climb_conf, f'enable_{climb_type}', False)]


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


class ScriptTask(GameUi, BaseActivity, SwitchSoul, ActivityShikigamiAssets):
    # key: climb type, value: run count
    count_map: dict[str, int] = {
        'pass': 0,
        'ap': 0,
        'boss': 0
    }
    page_map: dict[str, game.Page] = {
        'pass': game.page_climb_act_pass,
        'ap': game.page_climb_act_ap,
        'boss': game.page_climb_act_boss,
    }
    # key: climb type, value: {status: value}
    check_map: dict[str, dict[Status, Any]] = {}

    climb_type: str = 'pass'
    run_idx: int = 0

    def put_status(self):
        """
        更新全局状态
        """
        # 超过运行时间
        if self.limit_time is not None and datetime.now() - self.start_time >= self.limit_time:
            logger.warning(f"Climb type {self.climb_type} time out")
            self.put_check(Status.TIME_OUT, True)
        # 次数达到限制
        if self.get_count() >= self.get_limit(self.config.activity_shikigami.general_climb):
            logger.info(f"Climb type {self.climb_type} count limit reached")
            self.put_check(Status.DOWN, True)

    def check(self, status: Status) -> Any:
        if len(self.check_map) == 0:
            self.check_map = {climb_type: {state: None for state in list(Status)} for climb_type in
                              get_run_order_list(self.config.activity_shikigami.general_climb)}
        return self.check_map[self.climb_type][status]

    def put_check(self, status: Status, value: Any):
        self.check_map[self.climb_type][status] = value

    def run(self) -> None:
        config = self.config.activity_shikigami
        self.limit_time: timedelta = config.general_climb.limit_time
        if isinstance(self.limit_time, time):
            self.limit_time = timedelta(hours=self.limit_time.hour, minutes=self.limit_time.minute,
                                        seconds=self.limit_time.second)
        # 初始化爬塔类型
        self.climb_type = get_run_order_list(config.general_climb)[0]
        while True:
            self.put_status()
            # 超时或全部完成则退出
            if self.check(Status.TIME_OUT) or self.check(Status.ALL_DOWN):
                break
            # 当前爬塔类型完成了, 切换下一个类型
            if self.check(Status.DOWN):
                self.switch_next()
                continue
            # 获取当前页面
            current_page = self.ui_get_current_page(False)
            # 检查是否已经切换御魂
            if not self.check(Status.ALREADY_SWITCH_SOUL):
                self.switch_soul(config.switch_soul_config)
                continue
            match current_page:
                # 庭院, 进入活动主界面
                case game.page_main:
                    self.home_main()
                # 活动主界面或副界面, 进入最终爬塔界面
                case game.page_climb_act | game.page_climb_act_2:
                    # self.ui_goto(game.page_climb_act_buff)
                    self.goto_act()
                # buff界面, 进入最终爬塔界面
                case game.page_climb_act_buff:
                    self.switch_buff(config.general_climb)
                    self.goto_act()
                # 最终爬塔界面
                case game.page_climb_act_pass | game.page_climb_act_ap | game.page_climb_act_boss:
                    if not self.check_can_run():
                        continue
                    self.lock_team(config.general_battle)
                    self.start_battle()
                case _:
                    if self.check(Status.GOTO_ACT_FAILED):
                        logger.warning(f'Climb type[{self.climb_type}] goto failed')
                        self.put_check(Status.DOWN, True)
                        continue
                    self.put_check(Status.GOTO_ACT_FAILED, True)
                    # 任何活动界面都没有识别到, 尝试主动前往爬塔活动
                    self.goto_act()
        # 返回庭院
        self.main_home()
        if config.general_climb.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def start_battle(self):
        # 点击战斗前随机休息
        if self.config.activity_shikigami.general_climb.random_sleep:
            random_sleep(probability=0.2)
        logger.info("Click battle")
        click_times, max_times = 0, 3
        while 1:
            self.screenshot()
            if self.is_in_battle(False):
                break
            if click_times >= max_times:
                if self.check(Status.ENTER_BATTLE_FAILED):
                    logger.warning(f'Climb {self.climb_type} cannot enter, maybe already end, try next')
                    self.put_check(Status.DOWN, True)
                    return
                logger.warning(f'Climb type {self.climb_type} enter fail, try reidentify')
                self.put_check(Status.ENTER_BATTLE_FAILED, True)
                return
            # 点击挑战
            if self.ocr_appear_click(self.O_FIRE, interval=2):
                click_times += 1
                continue
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

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 通用战斗结束判断
        self.device.stuck_record_add("BATTLE_STATUS_S")
        self.device.click_record_clear()
        logger.info("Start battle process")

        for btn in (self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM):
            btn.name = "BATTLE_RANDOM"
        ok_cnt, max_retry = 0, 5
        while 1:
            sleep(0.5)
            self.screenshot()
            # 已经回到对应挑战界面
            if self.ui_page_appear(self.page_map[self.climb_type]):
                break
            # 达到最大重试次数且还没有识别到活动界面
            if ok_cnt > max_retry:
                # 跳出循环交由外部处理
                break
            # 失败
            if self.appear(self.I_FALSE):
                logger.warning("False battle")
                self.ui_click_until_smt_disappear(self.random_reward_click(click_now=False), self.I_FALSE, interval=1.5)
                return False
            # 奖励界面
            if self.ui_page_appear(game.page_reward):
                logger.info(f'Battle end, try close {ok_cnt}')
                self.random_reward_click(exclude_click=[self.C_RANDOM_BOTTOM])
                ok_cnt += 1
                continue
            # 已经不在战斗中了, 且奖励也识别过了还不在活动界面, 则随机点击
            if ok_cnt > 0 and not self.ui_page_appear(game.page_battle_auto):
                self.random_reward_click(exclude_click=[self.C_RANDOM_BOTTOM])
                ok_cnt += 1
                continue
            # 战斗中随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()
        return True

    def switch_soul(self, conf: SwitchSoulConfig):
        """
        根据当前爬塔类型自动切换御魂
        :param conf: 切换御魂配置
        :return:
        """
        if self.check(Status.ALREADY_SWITCH_SOUL):
            return
        self.put_check(Status.ALREADY_SWITCH_SOUL, True)
        enable_switch = getattr(conf, f"enable_switch_{self.climb_type}", False)
        enable_by_name = getattr(conf, f"enable_switch_{self.climb_type}_by_name", False)
        if enable_switch or enable_by_name:
            self.ui_goto(game.page_shikigami_records)
        if enable_by_name:
            group_name = getattr(conf, f"{self.climb_type}_group_team_name", '-1,-1')
            if not group_name or len(group_name.split(',')) != 2:
                raise ValueError('switch soul by name must be 2 length')
            group, team = group_name.split(",")
            self.run_switch_soul_by_name(group, team)
        elif enable_switch:
            group_team = getattr(conf, f"{self.climb_type}_group_team", '-1,-1')
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
        logger.hr(f'Check the {self.climb_type}', 3)
        if not self.wait_until_appear(self.O_FIRE, wait_time=5):
            logger.info(f'Detect fire fail, try next')
            self.put_check(Status.DOWN, True)
            return False
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
        self.put_check(Status.DOWN, remain_times <= 0)
        return remain_times > 0

    def get_limit(self, climb_conf: GeneralClimb) -> int:
        """
        获取配置中当前爬塔类型次数限制
        :param climb_conf: 爬塔配置
        :return: 限制次数
        """
        limit = getattr(climb_conf, f'{self.climb_type}_limit', 0)
        return 0 if not limit else limit

    def switch_next(self):
        """
        切换下一种爬塔类型
        :return: True 切换成功 or False
        """
        self.run_idx += 1
        climb_type_list = get_run_order_list(self.config.activity_shikigami.general_climb)
        if self.run_idx >= len(climb_type_list):
            logger.info('All climbing activities have been completed')
            self.put_check(Status.ALL_DOWN, True)
            return
        # 切换爬塔类型了, 恢复所有状态
        self.climb_type = climb_type_list[self.run_idx]
        self.current_count = 0
        self.put_check(Status.ALREADY_SWITCH_SOUL, False)
        self.put_check(Status.ALREADY_LOCK_TEAM, False)
        self.put_check(Status.GOTO_ACT_FAILED, False)
        self.put_check(Status.ENTER_BATTLE_FAILED, False)
        logger.hr(f'Climb type switch to {self.climb_type}', 2)

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
                   random_click_swipt_enable=getattr(conf.general_battle, f'enable_{self.climb_type}_anti_detect',
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

    def goto_act(self):
        self.ui_goto(self.page_map[self.climb_type], timeout=20)

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


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas3')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
