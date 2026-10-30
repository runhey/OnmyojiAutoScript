"""Offline invitation scheduling tests: no Config/Device initialization or game input."""
import json
import unittest
from datetime import datetime, timedelta, time
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from unittest.mock import Mock, patch

from module.config.config import Config
from tasks.base_task import BaseTask
from tasks.GlobalGame.config_emergency import Emergency, FriendInvitation


class InvitationScheduleTests(unittest.TestCase):
    NOW = datetime(2026, 10, 30, 16, 0, 0)

    def make_task(self, policy=FriendInvitation.ACCEPT, enabled=True, jade=False, food=False):
        task = BaseTask.__new__(BaseTask)
        task.start_time = self.NOW - timedelta(hours=1)
        task.config = SimpleNamespace(global_game=SimpleNamespace(emergency=Emergency(
            friend_invitation=policy, wanted_after_invitation=enabled)))
        task.device = SimpleNamespace(image=None, detect_record={'battle'}, screenshot=Mock())
        task.set_next_run = Mock()
        task.appear_then_click = Mock(return_value=True)
        task._invitation_checks = 0

        def appear(target, **kwargs):
            if target is task.I_G_ACCEPT:
                task._invitation_checks += 1
                return task._invitation_checks <= (3 if policy != FriendInvitation.ACCEPT else 2)
            if target is task.I_G_JADE:
                return jade
            if target in (task.I_G_CAT_FOOD, task.I_G_DOG_FOOD):
                return food
            # First loop sees the reject/ignore button, then it disappears.
            task._other_checks = getattr(task, '_other_checks', 0) + 1
            return task._other_checks == 1

        task.appear = Mock(side_effect=appear)
        return task

    def handle(self, task):
        with patch('tasks.base_task.datetime') as clock:
            clock.now.return_value = self.NOW
            self.assertTrue(task._burst())

    def test_accept_sets_now_without_server_override(self):
        task = self.make_task()
        self.handle(task)
        task.set_next_run.assert_called_once_with(task='WantedQuests', target=self.NOW, server=False)
        self.assertEqual(task.device.detect_record, {'battle'})

    def test_switch_off_keeps_original_schedule(self):
        task = self.make_task(enabled=False)
        self.handle(task)
        task.appear_then_click.assert_called()
        task.set_next_run.assert_not_called()

    def test_no_popup_does_not_schedule(self):
        task = self.make_task()
        task.appear.return_value = False
        task.appear.side_effect = None
        self.assertFalse(task._burst())
        task.set_next_run.assert_not_called()
        task.device.screenshot.assert_not_called()

    def test_popup_gone_before_actual_click_does_not_schedule(self):
        task = self.make_task()
        task.appear.side_effect = [True, False]
        self.handle(task)
        task.appear_then_click.assert_not_called()
        task.set_next_run.assert_not_called()

    def test_failed_click_does_not_schedule(self):
        task = self.make_task()
        task.appear_then_click.return_value = False
        self.handle(task)
        task.set_next_run.assert_not_called()

    def test_reject_and_ignore_do_not_schedule(self):
        for policy in (FriendInvitation.REJECT, FriendInvitation.IGNORE):
            with self.subTest(policy=policy):
                task = self.make_task(policy=policy)
                self.handle(task)
                task.set_next_run.assert_not_called()

    def test_filtered_accepts_schedule_but_filtered_ignores_do_not(self):
        for policy, jade, food, accepts in (
            (FriendInvitation.ONLY_JADE, True, False, True),
            (FriendInvitation.ONLY_JADE, False, False, False),
            (FriendInvitation.JADE_AND_FOOD, False, True, True),
            (FriendInvitation.JADE_AND_FOOD, False, False, False),
        ):
            with self.subTest(policy=policy, jade=jade, food=food):
                task = self.make_task(policy=policy, jade=jade, food=food)
                self.handle(task)
                self.assertEqual(task.set_next_run.call_count, int(accepts))

    def test_schedule_after_dialog_closure_only(self):
        task = self.make_task()
        def click(*args, **kwargs):
            task.set_next_run.assert_not_called()
            return True
        task.appear_then_click.side_effect = click
        self.handle(task)
        task.set_next_run.assert_called_once()

    def test_default_enabled_and_translations_exist(self):
        self.assertTrue(Emergency().wanted_after_invitation)
        root = Path(__file__).resolve().parents[3]
        for lang in ('zh-CN', 'en-US'):
            data = json.loads((root / 'assets/i18n' / (lang + '.json')).read_text(encoding='utf-8'))
            self.assertIn('wanted_after_invitation', data)
            self.assertIn('wanted_after_invitation_help', data)

    def test_real_scheduling_keeps_priority_and_enable_and_ignores_forced_time(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                scheduler = SimpleNamespace(enable=enabled, priority=7,
                    next_run=self.NOW + timedelta(days=1),
                    server_update=time(18), delay_date=1, float_time=time(2))
                config = SimpleNamespace(reload=Mock(), save=Mock(), lock_config=Lock(),
                    model=SimpleNamespace(wanted_quests=SimpleNamespace(scheduler=scheduler)))
                # Real BaseTask -> Config.task_delay path, with in-memory config only.
                config.task_delay = lambda *a, **k: Config.task_delay(config, *a, **k)
                task = self.make_task()
                task.config.model = config.model
                task.config.task_delay = config.task_delay
                task.set_next_run = lambda *a, **k: BaseTask.set_next_run(task, *a, **k)
                self.handle(task)
                self.assertEqual(scheduler.next_run, self.NOW)
                self.assertEqual(scheduler.priority, 7)
                self.assertEqual(scheduler.enable, enabled)
                config.save.assert_called_once()


if __name__ == '__main__':
    unittest.main()
