# This Python file uses the following encoding: utf-8
import copy
import re
import time

from module.base.timer import Timer
from module.exception import (GameNotRunningError, GamePageUnknownError,
                              GameStuckError, GameTooManyClickError, TaskEnd)
from module.logger import logger
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_guild, page_main
from tasks.GuildShardDonation.assets import GuildShardDonationAssets


class ScriptTask(GameUi, GuildShardDonationAssets):
    """向指定寮友捐赠一片指定 SSR/SP 式神碎片。"""

    TASK_NAME = "GuildShardDonation"
    MAX_SCAN_ROUNDS = 3
    BOTTOM_STABLE_SWIPES = 5
    PAGE_TIMEOUT = 20
    SCAN_TIMEOUT = 90

    def run(self):
        config = self.config.guild_shard_donation.donation_config
        self.target_player = config.target_player.strip()
        self.target_shard = config.target_shard.strip()
        self.test_mode = config.test_mode

        if not self.target_player or not self.target_shard:
            logger.error("碎片捐赠配置不完整：目标玩家昵称和碎片名称均不能为空")
            self._finish(False)

        try:
            for round_index in range(self.MAX_SCAN_ROUNDS):
                logger.hr(f"碎片捐赠扫描 {round_index + 1}/{self.MAX_SCAN_ROUNDS}", level=1)
                self._enter_prayer_page()
                target = self._scan_for_player()
                if target is None:
                    logger.warning("本轮完整扫描未找到目标玩家：%s", self.target_player)
                    self._return_to_main()
                    continue

                if not self._click_give_on_same_row(target):
                    logger.info("目标玩家同行没有‘赠予’按钮，按成功结束")
                    self._return_to_main()
                    self._finish(True)

                message = self._wait_and_read_confirm_dialog()
                if message is None or not self._confirm_message_is_safe(message):
                    logger.error("确认弹窗安全校验失败，取消捐赠。OCR=%r", message)
                    self._cancel_confirm_dialog()
                    self._return_to_main()
                    self._finish(False)

                if self.test_mode:
                    logger.info("测试模式：确认信息一致，取消弹窗，不执行真实捐赠")
                    self._cancel_confirm_dialog()
                    self._return_to_main()
                    self._finish(True)

                self.ui_click_until_disappear(self.I_CONFIRM)
                if not self._wait_and_close_reward():
                    logger.error("点击确定后未能确认奖励界面，为防止重复捐赠按失败结束")
                    self._return_to_main()
                    self._finish(False)

                self._return_to_main()
                logger.info("已成功向 %s 捐赠一片 %s 碎片", self.target_player, self.target_shard)
                self._finish(True)

            logger.info("三轮完整扫描均未找到目标玩家，按成功结束")
            self._return_to_main()
            self._finish(True)
        except TaskEnd:
            raise
        except (GameNotRunningError, GamePageUnknownError,
                GameStuckError, GameTooManyClickError):
            # 这些异常必须交给 OAS 外层调度器处理；外层会调用 Restart，
            # 负责启动模拟器/游戏、登录并回到庭院。
            raise
        except Exception:
            logger.exception("碎片捐赠任务发生未处理异常")
            try:
                self._return_to_main()
            except Exception:
                logger.exception("异常后无法安全返回庭院")
            self._finish(False)

    def _enter_prayer_page(self):
        self.ui_get_current_page()
        self.ui_goto(page_guild)

        timer = Timer(self.PAGE_TIMEOUT).start()
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_RECEIVED_POPUP):
                logger.info("检测到被捐赠状态弹窗，关闭后继续")
                self.click(self.C_RECEIVED_POPUP_CLOSE)
                time.sleep(1)
                continue
            if self.appear(self.I_PRAYER_PAGE):
                return
            if self.appear_then_click(self.I_PRAYER_ENTRY, interval=1):
                time.sleep(1)
                continue
            time.sleep(0.5)
        raise RuntimeError("进入祈愿页面超时")

    @staticmethod
    def _normalize_nickname(text):
        return text.strip()

    @staticmethod
    def _nickname_distance(left, right):
        """Return the edit distance, stopping once more than one edit is needed."""
        if abs(len(left) - len(right)) > 1:
            return 2
        previous = list(range(len(right) + 1))
        for row, left_char in enumerate(left, 1):
            current = [row]
            for column, right_char in enumerate(right, 1):
                current.append(min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (left_char != right_char),
                ))
            if min(current) > 1:
                return 2
            previous = current
        return previous[-1]

    def _read_visible_names(self):
        results = self.O_PLAYER_NAMES.detect_and_ocr(self.device.image)
        roi_x, roi_y, _, _ = self.O_PLAYER_NAMES.roi
        names = []
        for result in results:
            text = self._normalize_nickname(result.ocr_text)
            if not text:
                continue
            box = result.box
            scale = getattr(self.O_PLAYER_NAMES, "scale", 1.0)
            center_y = roi_y + float(box[:, 1].mean()) / scale
            names.append({"text": text, "center_y": center_y, "box": box, "roi_x": roi_x, "roi_y": roi_y})
        names.sort(key=lambda item: item["center_y"])
        logger.info("当前可见昵称 OCR：%s", [item["text"] for item in names])
        return names

    def _find_target_in(self, visible):
        """Find the configured player in one OCR sample."""
        for item in visible:
            if item["text"] == self.target_player:
                logger.info("严格匹配到目标玩家：%s，y=%.1f", item["text"], item["center_y"])
                return item

        # Chinese OCR occasionally confuses one visually similar character
        # (for example 困 -> 因). Accept only one unique, same-length,
        # one-character candidate. The confirmation dialog remains strict.
        fuzzy = [
            item for item in visible
            if len(item["text"]) == len(self.target_player)
            and re.findall(r"\d+", item["text"]) == re.findall(r"\d+", self.target_player)
            and self._nickname_distance(item["text"], self.target_player) == 1
        ]
        if len(fuzzy) == 1:
            logger.warning(
                "OCR 单字符容错匹配目标玩家：%s -> %s，y=%.1f",
                fuzzy[0]["text"], self.target_player, fuzzy[0]["center_y"],
            )
            return fuzzy[0]
        if len(fuzzy) > 1:
            logger.warning("存在多个昵称近似匹配，为安全起见继续扫描：%s",
                           [item["text"] for item in fuzzy])
        return None

    def _scan_for_player(self):
        timer = Timer(self.SCAN_TIMEOUT).start()
        previous_signature = None
        stable_count = 0
        self.device.click_record_clear()
        self.device.stuck_record_clear()

        while not timer.reached():
            self.screenshot()
            visible = self._read_visible_names()
            target = self._find_target_in(visible)
            if target is not None:
                return target

            signature = tuple(item["text"] for item in visible)
            # 连续滚动是这个任务的正常行为。直接调用设备滑动，避免通用控件的
            # “同一控件点击过多”保护把列表扫描误判为死循环。
            x1, y1, x2, y2 = self.S_PRAYER_LIST_UP.coord()
            swipe_started = time.monotonic()
            self.device.swipe(p1=(x1, y1), p2=(x2, y2))

            # Sample at 0.8s, 1.0s and 1.4s after the swipe. If a sample sees the
            # target, wait another 0.5s and OCR again; only that confirmed, fresh
            # position may be used to locate the Give button.
            after_swipe = []
            confirmed_target = None
            for sample_index, sample_at in enumerate((0.8, 1.0, 1.4), 1):
                remaining = sample_at - (time.monotonic() - swipe_started)
                if remaining > 0:
                    time.sleep(remaining)
                self.screenshot()
                after_swipe = self._read_visible_names()
                logger.info("滑动后 OCR 采样 %d/3（目标时间 %.1fs）", sample_index, sample_at)
                target = self._find_target_in(after_swipe)
                if target is not None:
                    logger.info("采样发现目标，等待 0.5 秒后重新识别并更新行坐标")
                    time.sleep(0.5)
                    self.screenshot()
                    confirmed_visible = self._read_visible_names()
                    confirmed_target = self._find_target_in(confirmed_visible)
                    if confirmed_target is not None:
                        logger.info("目标玩家复核成功，使用最新坐标 y=%.1f",
                                    confirmed_target["center_y"])
                    else:
                        logger.info("等待 0.5 秒后未再次识别到目标，继续滑动")
                    break

            if confirmed_target is not None:
                return confirmed_target

            # Keep consecutive swipes at least 1.5 seconds apart.
            remaining = 1.5 - (time.monotonic() - swipe_started)
            if remaining > 0:
                time.sleep(remaining)
            after_signature = tuple(item["text"] for item in after_swipe)

            if after_signature == signature and after_signature == previous_signature:
                stable_count += 1
            elif after_signature == signature:
                stable_count = 1
            else:
                stable_count = 0
            previous_signature = after_signature

            if stable_count >= self.BOTTOM_STABLE_SWIPES:
                logger.info("连续五次滑动后的昵称列表完全相同，判定已到列表底部")
                return None

        raise RuntimeError("祈愿列表扫描超时，无法可靠判定到底")

    def _click_give_on_same_row(self, target):
        center_y = int(round(target["center_y"]))
        top = max(125, center_y - 50)
        height = min(105, 500 - top)
        give = copy.deepcopy(self.I_GIVE)
        give.roi_back = (800, top, 330, height)
        self.screenshot()
        if not self.appear(give):
            return False
        logger.info("在目标玩家同行检测到‘赠予’按钮")
        self.click(give)
        return True

    def _wait_and_read_confirm_dialog(self):
        timer = Timer(12).start()
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_CONFIRM_DIALOG):
                text = self.O_CONFIRM_MESSAGE.detect_text(self.device.image)
                logger.info("确认弹窗 OCR：%r", text)
                return text
            time.sleep(0.5)
        return None

    @staticmethod
    def _normalize_confirm_text(text):
        text = re.sub(r"\s+", "", text or "")
        return text.translate(str.maketrans({"（": "(", "）": ")", "？": "?"}))

    def _confirm_message_is_safe(self, text):
        normalized = self._normalize_confirm_text(text)
        match = re.fullmatch(r"确认将(.+?)\(碎片\)赠送给(.+?)\?", normalized)
        if not match:
            logger.error("确认文案不符合固定安全句式：%r", normalized)
            return False
        shard_name, player_name = match.groups()
        shard_ok = shard_name == self.target_shard
        player_ok = player_name == self.target_player
        logger.info("确认弹窗字段校验：碎片=%r(%s)，玩家=%r(%s)",
                    shard_name, shard_ok, player_name, player_ok)
        return shard_ok and player_ok

    def _cancel_confirm_dialog(self):
        self.screenshot()
        if self.appear(self.I_CANCEL):
            self.ui_click_until_disappear(self.I_CANCEL)
        else:
            logger.warning("未找到专用取消按钮，尝试通过通用返回恢复")

    def _wait_and_close_reward(self):
        timer = Timer(15).start()
        while not timer.reached():
            self.screenshot()
            if self.ui_reward_appear_click():
                time.sleep(1)
                return True
            if self.appear(self.I_REWARD):
                self.click(self.C_REWARD_CLOSE)
                time.sleep(1)
                return True
            time.sleep(0.5)
        return False

    def _return_to_main(self):
        self.ui_get_current_page()
        self.ui_goto(page_main)

    def _finish(self, success):
        self.set_next_run(self.TASK_NAME, success=success, finish=True)
        raise TaskEnd(self.TASK_NAME)
