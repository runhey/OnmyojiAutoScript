# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum, auto
from time import sleep
from datetime import datetime, timedelta
import cv2
import numpy as np
import random
from typing import Any
from cached_property import cached_property

from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.ocr import RuleOcr
from module.base.protect import random_sleep
from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger

from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.config import SwitchSoulConfig, GeneralBattleConfig, ActivityShikigami
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.BaseActivity.config_activity import GeneralClimb
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
import tasks.Component.GeneralBattle.config_general_battle
import tasks.ActivityShikigami.page as game


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


class LimitTimeOut(Exception):
    pass


class LimitCountOut(Exception):
    pass


class StateMachine(BaseTask):
    run_idx: int = 0  # 当前爬塔类型
    _count_map = None

    @cached_property
    def conf(self) -> GeneralClimb:
        return self.config.model.activity_shikigami

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

    # ----------------------------------------------------
    def put_status(self):
        """
        更新全局状态
        """

        def get_count(self) -> int:
            return self.count_map[self.climb_type]

        def get_limit(self) -> int:
            limit = getattr(self.conf.general_climb, f'{self.climb_type}_limit', 0)
            return 0 if not limit else limit

        # 超过运行时间
        if self.limit_time is not None and datetime.now() - self.start_time >= self.limit_time:
            logger.info(f"Climb type {self.climb_type} time out")
            raise LimitTimeOut
        # 次数达到限制
        if get_count(self) >= get_limit(self):
            logger.info(f"Climb type {self.climb_type} count limit reached")
            raise LimitCountOut

    def switch_next(self):
        """
        切换下一种爬塔类型
        :return: True 切换成功 or False
        """
        self.run_idx += 1
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            logger.info('All climbing activities have been completed')
            return False
        # 切换爬塔类型了, 恢复所有状态
        self.current_count = 0
        logger.hr(f'Climb switch to {self.climb_type}', 2)
        return True


class ScriptTask(StateMachine, GameUi, BaseActivity, SwitchSoul, ActivityShikigamiAssets):
    """
    更新前请先看 ./README.md
    """

    def run(self) -> None:
        self.limit_time: timedelta = self.conf.general_climb.limit_time_v
        #
        for climb_type in self.conf.general_climb.run_sequence_v:
            # 2026.04.04>>>----------------------------------------------------------------
            if climb_type not in ['ap', 'ap100']:
                # `switch_next()` 在下方 finally 中才会增 run_idx, 这里 continue 会跳过 finally,
                # 导致 self.climb_type (= run_sequence_v[run_idx]) 与循环变量 climb_type 失步,
                # 之后 _run_ap 里 check_tickets_enough/lock_team/switch_soul 等都会读到错误的 climb_type.
                # 这里手动同步 run_idx, 保证后续 self.climb_type 正确.
                self.run_idx += 1
                continue
            # 2026.04.04<<<----------------------------------------------------------------
            # 进入到活动的主页面，不是具体的战斗页面
            self.ui_get_current_page()
            self.ui_goto(game.page_climb_act)
            try:
                method_func = getattr(self, f'_run_{climb_type}')
                method_func()
            except LimitCountOut as e:
                self.ui_clicks([self.I_UI_BACK_YELLOW, self.I_BACK_AP], stop=self.I_TO_BATTLE_MAIN, interval=1)
            except LimitTimeOut as e:
                break
            finally:
                # 切换下一个爬塔类型
                self.switch_next()

        # 返回庭院
        logger.hr("Exit Shikigami", 2)
        self.ui_get_current_page(False)
        self.ui_goto(game.page_main)
        if self.conf.general_climb.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def _run_pass(self):
        """
            更新前请先看 ./README.md
        """
        logger.hr(f'Start run climb type PASS', 1)
        self.ui_clicks([self.I_TO_BATTLE_MAIN, self.I_TO_BATTLE_MAIN_2],
                       stop=self.I_CHECK_BATTLE_MAIN, interval=1)
        self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS, self.I_CHECK_BATTLE_MAIN)
        self.switch_climb_mode_in_game('pass')

        ocr_limit_timer = Timer(1).start()
        click_limit_timer = Timer(4).start()
        while 1:
            self.screenshot()
            self.put_status()
            # --------------------------------------------------------------
            if (self.appear_then_click(self.I_UI_CONFIRM, interval=0.5)
                    or self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=0.5)):
                continue
            if self.ui_reward_appear_click():
                continue
            if not ocr_limit_timer.reached():
                continue
            ocr_limit_timer.reset()
            if not self.ocr_appear(self.O_FIRE):
                continue
            #  --------------------------------------------------------------
            self.lock_team(self.conf.general_battle)
            if not self.check_tickets_enough():
                logger.warning(f'No tickets left, wait for next time')
                break
            if self.conf.general_climb.random_sleep:
                random_sleep(probability=0.2)
            if self.start_battle():
                continue

        self.ui_clicks([self.I_UI_BACK_YELLOW, self.I_BACK_AP], stop=self.I_TO_BATTLE_MAIN, interval=1)

    def _run_ap(self):
        """
        AP 槽位现在分两种子模式, 在主战场上 OCR 资源后再决定进入哪条:
            - 门票爬塔 (remain_pass2 > 0):
                主战场 -> ticket_door -> ticket_enter -> 战斗界面 (I_CHECK_BATTLE_MAIN)
                资源闸口: O_REMAIN_PASS2  (走 self.check_tickets_enough, 因为 self.climb_type='ap')
            - 体力爬塔 (remain_pass2 == 0 且 remain_ap > 0):
                主战场 -> 点击 I_TO_BATTLE_MAIN_2 -> 战斗界面 (I_CHECK_BATTLE_MAIN_2)
                资源闸口: O_REMAIN_AP    (走 self._check_ap_enough)
            - 都没有: 直接退出
        更新前请先看 ./README.md
        """
        logger.hr(f'Start run climb type AP')

        # 1) 进入主战场
        self._goto_main_battlefield()

        # 2) 在主战场 OCR 资源, 决定走哪条子流程
        self.screenshot()
        pass_count = self.O_REMAIN_PASS2.ocr_digit(self.device.image)
        ap_count = self.O_REMAIN_AP.ocr_digit(self.device.image)
        logger.attr('Resources on 主战场', f'tickets={pass_count}, ap={ap_count}')

        if pass_count > 0:
            logger.info(f'Subflow=ticket (pass tickets={pass_count})')
            self._click_ticket_door_to_battle_area()
            self._click_ticket_enter_to_battle_main()
            self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS, self.I_CHECK_BATTLE_MAIN)
            # SWITCH SOUL 后会回退到活动战斗区域, 需要重新点击 ticket_enter 进入战斗准备界面
            self._click_ticket_enter_to_battle_main()
            check_battle_image = self.I_CHECK_BATTLE_MAIN
            gate = self.check_tickets_enough  # self.climb_type='ap' -> O_REMAIN_PASS2
            gate_label = 'tickets'
            # start_battle 失败 -> 退回活动战斗区域, 重新点 ticket_enter (可能选到另一只怪)
            def battle_fail_recover():
                self._recover_to_battle_area_after_failed_battle()
                self._click_ticket_enter_to_battle_main()
        elif ap_count > 0:
            logger.info(f'Subflow=stamina (ap={ap_count})')
            self.ui_click(self.I_TO_BATTLE_MAIN_2, stop=self.I_CHECK_BATTLE_MAIN_2, interval=1.5)
            self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS, self.I_CHECK_BATTLE_MAIN_2)
            check_battle_image = self.I_CHECK_BATTLE_MAIN_2
            gate = self._check_ap_enough
            gate_label = 'AP'
            # 体力爬塔暂无怪物可选/换关概念, 失败时不做特殊回退
            def battle_fail_recover():
                pass
        else:
            logger.warning(f'No tickets and no AP, exit AP task')
            self.ui_clicks([self.I_UI_BACK_YELLOW, self.I_BACK_AP], stop=self.I_TO_BATTLE_MAIN, interval=1)
            return

        # 3) 战斗循环 (两种子模式共用)
        ocr_limit_timer = Timer(1).start()
        while 1:
            self.screenshot()
            self.put_status()
            # --------------------------------------------------------------
            if not ocr_limit_timer.reached():
                continue
            ocr_limit_timer.reset()
            if not self.ocr_appear(self.O_FIRE):
                self.appear_then_click(check_battle_image, interval=4)
                continue
            #  --------------------------------------------------------------
            self.lock_team(self.conf.general_battle)
            if not gate():
                logger.warning(f'No {gate_label} left, wait for next time')
                break
            if self.conf.general_climb.random_sleep:
                random_sleep(probability=0.2)
            if self.start_battle():
                continue
            # start_battle 失败: 模式相关回退后再下一轮
            battle_fail_recover()

        self.ui_clicks([self.I_UI_BACK_YELLOW, self.I_BACK_AP], stop=self.I_TO_BATTLE_MAIN, interval=1)

    def _run_boss(self):
        """
        更新前请先看 ./README.md
        """
        logger.hr(f'Start run climb type BOSS')

    def _run_ap100(self):
        """
        100-体力 (雪山修行) 子流程:
            1) _goto_main_battlefield -> 主战场 (左侧栏可见 I_AP_100_CHECK = 雪山修行 入口)
            2) 进入前先 OCR O_REMAIN_AP100 (主战场左侧栏剩余次数), 0 则跳过, 不浪费时间进入
            3) ui_click(I_AP_100_CHECK, stop=I_AP_100_CHECK_MAIN) -> AP100 战斗界面
            4) switch_soul (使用 ap100_group_team 配置, cur_img=I_AP_100_CHECK_MAIN)
            5) 战斗循环, 闸口 = O_REMAIN_AP100_MAIN > 0 (这是 AP100 战斗界面内的剩余次数)
            6) 退回到活动主页
        更新前请先看 ./README.md
        """
        logger.hr(f'Start run climb type AP100')

        # 1) 主战场
        self._goto_main_battlefield()

        # 2) 进入前先确认还有次数; 没有就直接退出, 让外层调度切到下一个 climb_type
        self.screenshot()
        pre_count = self.O_REMAIN_AP100.ocr_digit(self.device.image)
        logger.attr('AP100 remaining (pre-enter)', pre_count)
        if pre_count <= 0:
            logger.warning('AP100: no attempts left, skip entry')
            return

        # 3) 进入 AP100 战斗界面
        self.ui_click(self.I_AP_100_CHECK, stop=self.I_AP_100_CHECK_MAIN, interval=1.5)

        # 4) switch_soul (self.climb_type='ap100', 会自动用 ap100_group_team 配置)
        # AP100 战斗界面进式神录的按钮位置和普通界面不一样, 优先找 climb_type 专属图,
        # 找不到才回退到通用的 I_BATTLE_MAIN_TO_RECORDS.
        records_btn = (getattr(self, f'I_{self.climb_type.upper()}_BATTLE_MAIN_TO_RECORDS', None)
                       or self.I_BATTLE_MAIN_TO_RECORDS)
        self.switch_soul(records_btn, self.I_AP_100_CHECK_MAIN)

        # 5) 战斗循环
        ocr_limit_timer = Timer(1).start()
        while 1:
            self.screenshot()
            self.put_status()
            # --------------------------------------------------------------
            if not ocr_limit_timer.reached():
                continue
            ocr_limit_timer.reset()
            if not self.ocr_appear(self.O_FIRE):
                self.appear_then_click(self.I_AP_100_CHECK_MAIN, interval=4)
                continue
            #  --------------------------------------------------------------
            self.lock_team(self.conf.general_battle)
            if not self._check_ap100_enough():
                logger.warning('No AP100 attempts left, wait for next time')
                break
            if self.conf.general_climb.random_sleep:
                random_sleep(probability=0.2)
            if self.start_battle():
                continue
            # AP100 是单关卡循环, 没有"换怪"的概念, start_battle 失败时不做特殊回退,
            # 由下一轮 ocr_appear(O_FIRE) / lock_team 重试.

        # 6) 退回活动主页
        self.ui_clicks([self.I_UI_BACK_YELLOW, self.I_BACK_AP], stop=self.I_TO_BATTLE_MAIN, interval=1)

    def start_battle(self):
        """
        :return: True 已进入并跑完一次战斗; False 多次点击挑战仍未能进入战斗 (调用方应进入回退流程).
        """
        click_times, max_times = 0, random.randint(4, 8)
        while 1:
            self.screenshot()
            if self.is_in_battle(False):
                break
            if click_times >= max_times:
                logger.warning(f'Climb {self.climb_type} cannot enter, maybe already end, try next')
                return False
            if (self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1) or
                    self.appear_then_click(self.I_UI_CONFIRM, interval=1) ):
                continue
            if self.ocr_appear_click(self.O_FIRE, interval=2):
                click_times += 1
                logger.info(f'Try click fire, remain times[{max_times - click_times}]')
                continue
        # 运行战斗
        self.run_general_battle(config=self.get_general_battle_conf())
        return True

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 通用战斗结束判断
        self.device.stuck_record_add("BATTLE_STATUS_S")
        self.device.click_record_clear()
        logger.info(f"Start {self.climb_type} battle process")
        self.count_map[self.climb_type] = self.current_count
        for btn in (self.C_RANDOM_LEFT, self.C_RANDOM_RIGHT, self.C_RANDOM_TOP, self.C_RANDOM_BOTTOM):
            btn.name = "BATTLE_RANDOM"
        ok_cnt, max_retry = 0, 8
        # Watchdog: 连续多少轮所有已知锚点都没识别到. 用于兜底 "点击屏幕继续" 类
        # 中间结算屏 -- 比如 AP100 大量御魂图标盖住 I_REWARD 锚点导致主流程死循环.
        no_progress_cnt = 0
        while 1:
            sleep(random.uniform(0.5, 1.5))
            self.screenshot()
            # 达到最大重试次数则直接交给上层处理
            if ok_cnt > max_retry:
                break
            # 识别到挑战说明已经退出战斗
            if ok_cnt > 0 and self.ocr_appear(self.O_FIRE):
                return True
            # 战斗失败
            if self.appear(self.I_FALSE):
                logger.warning("Battle failed")
                self.ui_click_until_smt_disappear(self.random_reward_click(click_now=False), self.I_FALSE, interval=1.5)
                return False
            # 战斗成功
            if self.appear_then_click(self.I_WIN, interval=2):
                no_progress_cnt = 0
                continue
            #  出现 “魂” 和 紫蛇皮
            if self.appear(self.I_REWARD) or self.appear(self.I_REWARD_PURPLE_SNAKE_SKIN) or \
                    self.appear(self.I_REWARD_GOLD) or self.appear(self.I_REWARD_GOLD_SNAKE_SKIN):
                self.random_reward_click(exclude_click=[self.C_RANDOM_TOP, self.C_RANDOM_LEFT])
                ok_cnt += 1
                no_progress_cnt = 0
                continue
            # 已经不在战斗中了, 且奖励也识别过了, 则随机点击
            if ok_cnt > 3 and not self.is_in_battle(False):
                self.random_reward_click(exclude_click=[self.C_RANDOM_TOP, self.C_RANDOM_LEFT])
                self.device.stuck_record_clear()
                ok_cnt += 1
                no_progress_cnt = 0
                continue
            # 战斗中随机滑动
            if ok_cnt == 0 and random_click_swipt_enable:
                self.random_click_swipt()
                no_progress_cnt = 0
                continue
            # Watchdog: 上面所有分支都没匹配到. 累计计数; 连续 5 轮 ~5 秒都没识别到任何已知锚点,
            # 且当前已不在战斗中, 说明屏幕大概率是 "点击屏幕继续" 这类 dismissable 中间屏
            # (比如 AP100 大量奖励图标遮住 I_REWARD), 强制 random-click 让流程继续.
            # is_in_battle 检查保证战斗中 (角色还在打) watchdog 不乱点.
            no_progress_cnt += 1
            if no_progress_cnt >= 5 and not self.is_in_battle(False):
                logger.warning(
                    f'battle_wait watchdog: no known marker for {no_progress_cnt} iters '
                    f'and not in battle, force random click to dismiss intermediate screen'
                )
                self.random_reward_click(exclude_click=[self.C_RANDOM_TOP, self.C_RANDOM_LEFT])
                ok_cnt += 1
                no_progress_cnt = 0
        return True

    def switch_soul(self, enter_button: RuleImage, cur_img: RuleImage):
        conf = self.conf.switch_soul_config
        enable_switch = getattr(conf, f"enable_switch_{self.climb_type}", False)
        enable_by_name = getattr(conf, f"enable_switch_{self.climb_type}_by_name", False)
        if not enable_switch and not enable_by_name:
            return
        logger.hr('Start switch soul', 2)
        conf.validate_switch_soul()
        self.ui_click(enter_button, stop=self.I_CHECK_RECORDS, interval=1)
        if enable_by_name:
            group, team = getattr(conf, f"{self.climb_type}_group_team_name").split(",")
            self.run_switch_soul_by_name(group, team)
        elif enable_switch:
            group_team = getattr(conf, f"{self.climb_type}_group_team")
            self.run_switch_soul(group_team)
        self.ui_click(self.I_UI_BACK_YELLOW, stop=cur_img, interval=1)

    def switch_climb_mode_in_game(self, mode: str = 'ap'):
        map_check = {
            'ap': self.I_CLIMB_MODE_AP,
            'pass': self.I_CLIMB_MODE_PASS,
        }
        logger.info(f'Switch climb mode to {mode}')
        self.ui_click(self.I_CLIMB_MODE_SWITCH, stop=map_check[mode], interval=1.9)

    def _enter_ticket_climb(self):
        """
        门票爬塔的完整入口流程 = 三个子步骤组合, 已分别抽出为独立方法以便其他子流程复用:
            0) _goto_main_battlefield()              -> 主战场 (出现 I_TO_BATTLE_MAIN_2)
            1) _click_ticket_door_to_battle_area()   -> 活动战斗区域 (出现 I_TICKET_ENTER)
            2) _click_ticket_enter_to_battle_main()  -> 门票爬塔战斗准备界面 (出现 I_CHECK_BATTLE_MAIN)
        每个子步骤都对后续阶段的标志位做了早退检查, 整体可重入.
        """
        self._goto_main_battlefield()
        self._click_ticket_door_to_battle_area()
        self._click_ticket_enter_to_battle_main()

    def _goto_main_battlefield(self) -> bool:
        """
        活动主页 -> 主战场. 用 I_TO_BATTLE_MAIN_2 (体力爬塔入口图标) 作为"已到达主战场"的稳定信号:
            - 它的 roi_back 较大, 比 I_TICKET_DOOR (40x39 小图标) 更不容易漏检.
            - I_TICKET_ENTER 阈值已下调到 0.65, 在活动主页上会假阳性, 不能用作早退信号.
        若已经在两种战斗界面之一 (I_CHECK_BATTLE_MAIN / I_CHECK_BATTLE_MAIN_2), 直接返回.
        :return: True 表示成功到达主战场或更深, False 表示点击次数耗尽.
        """
        main_clicks, max_main_clicks = 0, 8
        while 1:
            self.screenshot()
            # 已经在两种战斗界面之一, 跳过
            if self.appear(self.I_CHECK_BATTLE_MAIN) or self.appear(self.I_CHECK_BATTLE_MAIN_2):
                logger.info('Already past main battlefield')
                return True
            # 看到主战场标志, 进入下一步
            if self.appear(self.I_TO_BATTLE_MAIN_2):
                return True
            if main_clicks >= max_main_clicks:
                logger.warning('Click I_TO_BATTLE_MAIN too many times without progress')
                return False
            if self.appear_then_click(self.I_TO_BATTLE_MAIN, interval=1.5):
                main_clicks += 1
                continue

    def _click_ticket_door_to_battle_area(self):
        """
        主战场点击 I_TICKET_DOOR_CLOSE 进入透视模式 (I_TICKET_DOOR_OPEN 可见).
        透视模式打开后, 战斗目标 (I_TICKET_ENTER / I_TICKET_ENTER_1) 才能识别.

        约束:
        - 至少点 I_TICKET_DOOR_CLOSE 1 次, 最多 5 次.
        - 肯定的"已切到 open 状态"信号 = I_TICKET_DOOR_OPEN 出现.
        - 硬迭代上限保证不死循环.

        若已身处战斗准备界面 (I_CHECK_BATTLE_MAIN), 兜底空操作返回.
        """
        if self.appear(self.I_CHECK_BATTLE_MAIN):
            logger.info('Already in battle main page, skip ticket door step')
            return

        door_clicks, max_door_clicks = 0, 5
        max_iters, iters = 30, 0
        while iters < max_iters:
            iters += 1
            self.screenshot()
            # 已切到透视模式开启状态, 进入下一步
            if self.appear(self.I_TICKET_DOOR_OPEN):
                logger.info('Ticket door open mode active')
                break
            if door_clicks >= max_door_clicks:
                break
            if self.appear_then_click(self.I_TICKET_DOOR_CLOSE, interval=1.5):
                door_clicks += 1
        logger.info(f'I_TICKET_DOOR_CLOSE clicked {door_clicks} times in {iters} iters')

    def _click_ticket_enter_to_battle_main(self):
        """
        点击战斗目标 (I_TICKET_ENTER 或 I_TICKET_ENTER_1, 两个变体, 任一可点就点),
        直到 I_CHECK_BATTLE_MAIN (战斗准备界面) 出现.

        前置条件: 已点过 I_TICKET_DOOR_CLOSE 切到透视模式开启 (这两个 enter 模板才会显现).
        模板都是 hex 边角, 不大且不易识别, 用 asset 默认阈值 0.8 + 最大点击次数兜底.

        若已在战斗准备界面, 立即返回. 用于:
            - _enter_ticket_climb 末尾, 完成最后一跳;
            - switch_soul 之后, 重新进入战斗准备界面;
            - start_battle 失败 + _recover_to_battle_area_after_failed_battle 之后, 重新选怪.
        """
        enter_clicks, max_enter_clicks = 0, 8
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_BATTLE_MAIN):
                logger.info('At ticket climb battle main page')
                return
            if enter_clicks >= max_enter_clicks:
                logger.warning('Click I_TICKET_ENTER (any variant) too many times, fallback')
                return
            # 两个变体, 任一可点就点 (列表顺序 = 优先级)
            if self.appear_then_click(self.I_TICKET_ENTER, interval=1.5):
                enter_clicks += 1
                continue
            if self.appear_then_click(self.I_TICKET_ENTER_1, interval=1.5):
                enter_clicks += 1
                continue

    def _recover_to_battle_area_after_failed_battle(self):
        """
        在门票爬塔战斗准备界面 (I_CHECK_BATTLE_MAIN) 反复点挑战仍进不了战斗时调用,
        回退一步到活动战斗区域 (door 点击之后的页面), 让下一轮可以重新选 ticket_enter
        指向的怪物 (可能是另外一只).
        以 "I_CHECK_BATTLE_MAIN 不再可见 + 至少点过一次 back" 作为退出信号.
        """
        logger.info('Recover: back from battle prep to ticket battle area, re-select monster')
        back_clicks, max_back_clicks = 0, 3
        while 1:
            self.screenshot()
            if back_clicks > 0 and not self.appear(self.I_CHECK_BATTLE_MAIN):
                return
            if back_clicks >= max_back_clicks:
                logger.warning('Recover: max back clicks reached without leaving battle prep')
                return
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1.2):
                back_clicks += 1
                continue

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """
        根据配置判断当前爬塔类型是否锁定阵容, 并执行锁定或解锁.
        不同 climb_type 的锁定按钮可能位置/外观不同 (例如 AP100 战斗界面与门票/体力爬塔不在同一处),
        因此优先按命名约定查找 climb_type 专属的图标:
            - I_<CLIMB_TYPE>_LOCK   (例: I_AP100_LOCK)
            - I_<CLIMB_TYPE>_UNLOCK (例: I_AP100_UNLOCK)
        若没有专属图标则回退到通用的 I_LOCK / I_UNLOCK.
        """
        lock_attr = f'I_{self.climb_type.upper()}_LOCK'
        unlock_attr = f'I_{self.climb_type.upper()}_UNLOCK'
        lock_img = getattr(self, lock_attr, None) or self.I_LOCK
        unlock_img = getattr(self, unlock_attr, None) or self.I_UNLOCK

        enable_preset = getattr(battle_conf, f"enable_{self.climb_type}_preset", False)
        if not enable_preset:
            logger.info(f'Lock {self.climb_type} team')
            self.ui_click(unlock_img, stop=lock_img, interval=1.5)
            return
        logger.info(f'Unlock {self.climb_type} team')
        self.ui_click(lock_img, stop=unlock_img, interval=1.5)

    def check_tickets_enough(self) -> bool:
        """
        判断当前爬塔门票是否足够
        :return: True 可以运行 or False
        """
        logger.hr(f'Check {self.climb_type} tickets')
        if not self.wait_until_appear(self.O_FIRE, wait_time=3):
            logger.warning(f'Detect fire fail, try reidentify')
            return False
        self.screenshot()
        remain_times = 0
        if self.climb_type == 'pass':
            remain_times = self.O_REMAIN_PASS.ocr_digit(self.device.image)
        if self.climb_type == 'ap':
            remain_times = self.O_REMAIN_PASS2.ocr_digit(self.device.image)
        if self.climb_type == 'boss':
            _, remain_times, _ = self.O_REMAIN_BOSS.ocr_digit_counter(self.device.image)
        if self.climb_type == 'ap100':
            remain_times = self.O_REMAIN_AP100.ocr_digit(self.device.image)
        return remain_times > 0

    def _check_ap_enough(self) -> bool:
        """
        体力爬塔子流程的资源闸口: OCR O_REMAIN_AP, > 0 即可继续战斗.
        和 check_tickets_enough 同型: 先 wait_until_appear(O_FIRE) 保证页面已稳定再 OCR.
        """
        logger.hr('Check ap stamina')
        if not self.wait_until_appear(self.O_FIRE, wait_time=3):
            logger.warning('Detect fire fail, try reidentify')
            return False
        self.screenshot()
        remain_times = self.O_REMAIN_AP.ocr_digit(self.device.image)
        return remain_times > 0

    def _check_ap100_enough(self) -> bool:
        """
        AP100 (雪山修行) 子流程战斗循环的资源闸口:
        在 AP100 战斗界面内 OCR O_REMAIN_AP100_MAIN, > 0 即可继续战斗.
        与入场前用的 O_REMAIN_AP100 (主战场左侧栏) 不同, 这个 OCR 的位置在 AP100 战斗界面的顶部.
        """
        logger.hr('Check ap100 attempts')
        if not self.wait_until_appear(self.O_FIRE, wait_time=3):
            logger.warning('Detect fire fail, try reidentify')
            return False
        self.screenshot()
        remain_times = self.O_REMAIN_AP100_MAIN.ocr_digit(self.device.image)
        return remain_times > 0

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

    c = Config('欢哥')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()


