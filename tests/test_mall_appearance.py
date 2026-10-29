"""Check both mall appearances and return paths without a device or OCR service."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from module.exception import GamePageUnknownError
from tasks.DailyTrifles.assets import DailyTriflesAssets
from tasks.DailyTrifles.page import page_store_gift_room
from tasks.DailyTrifles.script_task import ScriptTask
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_mall, page_mall_recommend
from tasks.GameUi.session import NavigatorSession
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.RichMan.mall.navbar import MallNavbar


def frame_with(*rules):
    """Build a synthetic frame using the unchanged asset positions."""
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    for rule in rules:
        template = rule.image
        x, y = rule.roi_front[:2]
        height, width = template.shape[:2]
        frame[y:y + height, x:x + width] = template
    return frame


class OfflineMallUi(GameUi):
    def __init__(self, mall_rule, state="mall"):
        # Skip real Config/Device setup; keep the production matcher and navigator.
        back = GlobalGameAssets.I_UI_BACK_YELLOW
        self.frames = {
            "mall": frame_with(mall_rule, back),
            "main": frame_with(GameUiAssets.I_CHECK_MAIN, GameUiAssets.I_MAIN_GOTO_MALL),
            "recommend": frame_with(GameUiAssets.I_CHECK_MALL_RECOMMEND, back),
            "gift": frame_with(DailyTriflesAssets.I_GIFT_RECOMMEND, back),
            "room": frame_with(back),
            "blank": frame_with(),
        }
        self.state = state
        self.after_sign = "gift"
        self.clicks = []
        self.screenshot_count = 0
        self.interval_timer = {}
        self.config = SimpleNamespace(
            daily_trifles=SimpleNamespace(
                trifles_config=SimpleNamespace(store_sign=True, buy_sushi_count=-1),
            ),
            script=SimpleNamespace(device=SimpleNamespace(control_method="minitouch")),
        )
        self.device = SimpleNamespace(
            image=self.frames[state],
            app_lost_login=lambda: False,
            app_is_running=lambda: True,
            get_orientation=lambda: None,
        )
        self.navigator = NavigatorSession(task_category="daily_trifles")
        self.navigator.bootstrap([page_main, page_mall, page_mall_recommend, page_store_gift_room])

    def screenshot(self):
        self.screenshot_count += 1
        if self.screenshot_count > 100:
            raise AssertionError("Mall navigation kept retrying")
        self.device.image = self.frames[self.state]
        return self.device.image

    def appear_then_click(self, target, **kwargs):
        if not self.appear(target):
            return False
        self.clicks.append(target)
        if target is self.I_UI_BACK_YELLOW:
            self.state = "main" if self.state == "mall" else "mall"
        elif target is self.I_MAIN_GOTO_MALL:
            self.state = "recommend"
        else:
            raise AssertionError(f"Unexpected click: {target}")
        return True

    def run_store_sign(self):
        # Leave the cached mall screenshot stale to check that return takes a new one.
        self.state = self.after_sign


class MallAppearanceTests(unittest.TestCase):
    variants = (GameUiAssets.I_CHECK_MALL, GameUiAssets.I_CHECK_MALL_PURPLE)

    def setUp(self):
        for target in ("tasks.GameUi.navigator.Timer.wait", "tasks.GameUi.navigator.time.sleep"):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_both_appearances_are_recognized_but_non_mall_is_not(self):
        for rule in self.variants:
            with self.subTest(rule=rule.name):
                task = OfflineMallUi(rule)
                self.assertTrue(task.confirm_page(page_mall))
                task.state = "main"
                self.assertFalse(task.confirm_page(page_mall, skip_first_screenshot=False))

    def test_entering_from_main_stops_at_either_mall_appearance(self):
        for rule in self.variants:
            with self.subTest(rule=rule.name):
                task = OfflineMallUi(rule, state="main")
                self.assertTrue(task.goto_page(page_mall))
                self.assertEqual(task.state, "mall")
                self.assertEqual(task.clicks, [task.I_MAIN_GOTO_MALL, task.I_UI_BACK_YELLOW])

    def test_return_does_not_click_back_when_already_in_mall(self):
        for rule in self.variants:
            with self.subTest(rule=rule.name):
                task = OfflineMallUi(rule)
                MallNavbar.back_mall(task)
                self.assertEqual(task.state, "mall")
                self.assertEqual(task.clicks, [])

    def test_daily_trifles_returns_from_gift_room_then_exits_to_main(self):
        for rule in self.variants:
            with self.subTest(rule=rule.name):
                task = OfflineMallUi(rule)
                ScriptTask.run_store(task)
                self.assertEqual(task.state, "main")
                self.assertEqual(task.clicks, [task.I_UI_BACK_YELLOW] * 2)

    def test_rich_man_returns_from_an_unregistered_shop_room(self):
        for rule in self.variants:
            with self.subTest(rule=rule.name):
                task = OfflineMallUi(rule, state="room")
                MallNavbar.back_mall(task)
                self.assertEqual(task.state, "mall")
                self.assertEqual(task.clicks, [task.I_UI_BACK_YELLOW])

    def test_unrecognized_return_page_raises_instead_of_finishing(self):
        for caller in (ScriptTask.run_store, MallNavbar.back_mall):
            with self.subTest(caller=caller.__qualname__):
                task = OfflineMallUi(self.variants[1], state="mall" if caller is ScriptTask.run_store else "blank")
                task.after_sign = "blank"
                with patch("tasks.GameUi.navigator.Timer") as timer:
                    timer.return_value.start.return_value.reached.return_value = True
                    with self.assertRaises(GamePageUnknownError):
                        caller(task)
                self.assertEqual(task.clicks, [])


if __name__ == "__main__":
    unittest.main()
