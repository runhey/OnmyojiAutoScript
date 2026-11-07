# -*- coding: utf-8 -*-
"""Regression tests for the interval throttle in ``BaseTask.appear``.

``appear()`` used to recreate the throttle ``Timer`` whenever a different
``interval`` was passed for the same control name. A freshly constructed
``Timer`` is not started, so ``reached()`` always returns ``True`` and the
throttle is silently bypassed. When several call sites act on the same
control in one frame this produces repeated clicks until
``GameTooManyClickError`` fires.
"""

import time
import unittest

import numpy as np

from tasks.base_task import BaseTask


class _AlwaysAppear:
    """Stub control that always matches, avoiding real template matching."""

    name = 'SOME_BUTTON'

    def match(self, image, threshold=None):
        return True

    def coord(self):
        return 100, 100


class _FakeDevice:
    def __init__(self):
        self.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.clicks = []

    def click(self, x, y, control_name=None):
        self.clicks.append(control_name)


def _make_task():
    task = BaseTask.__new__(BaseTask)
    task.interval_timer = {}
    task.device = _FakeDevice()
    return task


class TestAppearIntervalThrottle(unittest.TestCase):
    def test_different_intervals_do_not_bypass_throttle(self):
        # Two call sites using 1s and 1.5s on the same control must still
        # share one running timer instead of resetting it on every call.
        task = _make_task()
        target = _AlwaysAppear()
        for _ in range(20):
            task.appear_then_click(target, interval=1)
            task.appear_then_click(target, interval=1.5)
        self.assertEqual(len(task.device.clicks), 1)

    def test_same_interval_is_throttled(self):
        task = _make_task()
        target = _AlwaysAppear()
        for _ in range(10):
            task.appear_then_click(target, interval=1.5)
        self.assertEqual(len(task.device.clicks), 1)

    def test_throttle_releases_after_interval(self):
        task = _make_task()
        target = _AlwaysAppear()
        task.appear_then_click(target, interval=0.05)
        task.appear_then_click(target, interval=0.05)
        self.assertEqual(len(task.device.clicks), 1)
        time.sleep(0.06)
        task.appear_then_click(target, interval=0.05)
        self.assertEqual(len(task.device.clicks), 2)


if __name__ == '__main__':
    unittest.main()
