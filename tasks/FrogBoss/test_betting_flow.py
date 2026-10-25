import unittest
from unittest.mock import patch

from module.exception import GameStuckError
from tasks.FrogBoss.script_task import ScriptTask


class FrameTimer:
    """Bound waits by simulated frames without sleeping or using a device."""

    def __init__(self, *_args):
        self.frames = 0

    def start(self):
        return self

    def reached(self):
        self.frames += 1
        return self.frames > 12


class BettingTask(ScriptTask):
    def __init__(self, frames):
        self.frames = iter(frames)
        self.visible = set()
        self.clicks = []

    def screenshot(self):
        self.visible = next(self.frames, self.visible)

    def appear(self, rule):
        return rule.name in self.visible

    def click(self, rule, interval=None):
        self.clicks.append(rule)
        return True

    def appear_then_click(self, rule, interval=None):
        if not self.appear(rule):
            return False
        return self.click(rule, interval=interval)


@patch('tasks.FrogBoss.script_task.Timer', FrameTimer)
class BettingFlowTests(unittest.TestCase):
    def test_reward_overlay_and_confirmation_hide_clickable_background(self):
        panel = {ScriptTask.I_GOLD_30.name, ScriptTask.I_BET_SURE.name}
        task = BettingTask([
            panel | {ScriptTask.I_GOLD_30_CHECK.name},
            panel,
            panel,
            panel | {ScriptTask.I_UI_CONFIRM.name},
            {ScriptTask.I_BETTED.name},
        ])
        task.confirm_bet()
        self.assertEqual([rule.name for rule in task.clicks], [
            ScriptTask.C_REWARD_2.name,
            'FB_GOLD_30_SELECT',
            ScriptTask.I_BET_SURE.name,
            ScriptTask.I_UI_CONFIRM.name,
        ])
        selection = task.clicks[1]
        x, y, width, height = ScriptTask.I_GOLD_30.roi_front
        sx, sy, sw, sh = selection.roi_front
        self.assertGreaterEqual(sx, x)
        self.assertLessEqual(sx + sw, x + width)
        self.assertGreaterEqual(sy, y)
        self.assertLess(sy + sh, y + height // 2)

    def test_cannot_submit_before_selecting_amount(self):
        task = BettingTask([{ScriptTask.I_BET_SURE.name}])
        with self.assertRaisesRegex(GameStuckError, 'gold_selected=False'):
            task.confirm_bet()
        self.assertEqual(task.clicks, [])

    def test_no_response_limits_submit_retries_without_reselecting_amount(self):
        panel = {ScriptTask.I_GOLD_30.name, ScriptTask.I_BET_SURE.name}
        task = BettingTask([panel])
        with self.assertRaisesRegex(GameStuckError, 'submit_attempts=3'):
            task.confirm_bet()
        self.assertEqual([rule.name for rule in task.clicks], [
            'FB_GOLD_30_SELECT',
            ScriptTask.I_BET_SURE.name,
            ScriptTask.I_BET_SURE.name,
            ScriptTask.I_BET_SURE.name,
        ])

    def test_already_betted_and_rest_end_without_clicking(self):
        for marker in (ScriptTask.I_BETTED, ScriptTask.I_FROG_BOSS_REST):
            with self.subTest(marker=marker.name):
                task = BettingTask([{marker.name}])
                task.confirm_bet()
                self.assertEqual(task.clicks, [])


if __name__ == '__main__':
    unittest.main()
