"""Exercise bounded island entry without a game or OCR service."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from module.exception import GameStuckError
from tasks.SixRealms.common import MoonSeaType
from tasks.SixRealms.moon_sea.map import MoonSeaMap


class OfflineMoonSea(MoonSeaMap):
    def __init__(self, enter_after=None, cancel_visible=False):
        # Skip Config/Device initialization, retaining the production click method.
        self.device = SimpleNamespace(click=self.record_click)
        self.now = 100.0
        self.frames = 0
        self.interval_timer = {}
        self.events = []
        self.enter_after = enter_after
        self.cancel_visible = cancel_visible

    def record_click(self, x, y, control_name):
        self.events.append((self.now, control_name))

    def screenshot(self):
        self.now += 0.25
        self.frames += 1
        if self.frames > 80:
            raise AssertionError("Island entry exceeded its timeout")

    def in_main(self):
        return self.enter_after is None or len(self.events) < self.enter_after

    def appear(self, rule, **kwargs):
        if rule is self.I_BACK_EXIT:
            return not self.in_main()
        if rule is self.I_UI_CANCEL:
            return self.cancel_visible
        return False

    def appear_then_click(self, rule, **kwargs):
        if not self.appear(rule):
            return False
        self.click(rule)
        return True


class IslandEntryTests(unittest.TestCase):
    def enter_unknown(self, task):
        with patch("module.base.timer.time.time", side_effect=lambda: task.now):
            task.enter_island(MoonSeaType.island100, (0, 0, 0, 0))

    def test_entry_stops_without_clicking_when_already_inside(self):
        task = OfflineMoonSea(enter_after=0)
        self.enter_unknown(task)
        self.assertEqual(task.events, [])

    def test_entry_cycles_in_order_with_one_shared_interval(self):
        task = OfflineMoonSea(enter_after=8)
        self.enter_unknown(task)
        self.assertEqual(
            [name for _, name in task.events],
            [f"island_enter_{number}" for number in (1, 2, 3, 4, 5, 6, 1, 2)],
        )
        for earlier, later in zip(task.events, task.events[1:]):
            self.assertGreaterEqual(later[0] - earlier[0], 1)

    def test_unrecognized_page_times_out_instead_of_clicking_forever(self):
        task = OfflineMoonSea()
        with self.assertRaisesRegex(GameStuckError, "Enter unknown island timeout"):
            self.enter_unknown(task)
        self.assertGreater(task.now, 115)
        self.assertLessEqual(task.now, 115.25)
        self.assertLessEqual(len(task.events), 15)

    def test_cancel_popup_obeys_interval_and_does_not_reset_timeout(self):
        task = OfflineMoonSea(cancel_visible=True)
        with self.assertRaises(GameStuckError):
            self.enter_unknown(task)
        self.assertTrue(task.events)
        self.assertTrue(all(name == task.I_UI_CANCEL.name for _, name in task.events))
        self.assertLessEqual(task.now, 115.25)
        for earlier, later in zip(task.events, task.events[1:]):
            self.assertGreaterEqual(later[0] - earlier[0], 1)


if __name__ == "__main__":
    unittest.main()
