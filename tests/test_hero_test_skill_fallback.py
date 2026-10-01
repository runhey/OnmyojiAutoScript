"""Exercise HeroTest selection loops without a Config, Device or running game."""

import itertools
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from module.atom.click import RuleClick
from tasks.HeroTest.config import SkillMode
from tasks.HeroTest.script_task import ScriptTask


class ScriptedHeroTest(ScriptTask):
    def __init__(self, *, mode=SkillMode.PVE, panel_visible=True, close_on_frame=None):
        # Skip BaseTask.__init__, which requires a real Config and Device.
        self.conf = SimpleNamespace(herotest=SimpleNamespace(skill_mode=mode))
        self.panel_visible = panel_visible
        self.close_on_frame = close_on_frame
        self.frames = 0
        self.visible_skills = []
        self.attempted_skills = []
        self.events = []

    def screenshot(self):
        self.frames += 1
        if self.frames > 3:
            raise AssertionError('Skill selection kept retrying after the timeout')
        if self.frames == self.close_on_frame:
            self.panel_visible = False

    def wait_until_appear(self, button, **kwargs):
        return self.appear(button)

    def appear(self, button, **kwargs):
        return button is self.I_BCMJ_SKILL_ADD_CONFIRM and self.panel_visible

    def appear_then_click(self, button, **kwargs):
        if button is self.I_BCMJ_SKILL_ADD_CONFIRM:
            if not self.panel_visible:
                return False
            self.events.append(('confirm', button))
            self.panel_visible = False
            return True
        self.attempted_skills.append(button)
        if any(button is skill for skill in self.visible_skills):
            self.events.append(('preferred', button))
            return True
        return False

    def click(self, button, **kwargs):
        self.events.append(('fallback', button))
        return True

    def ui_click_until_disappear(self, button, **kwargs):
        self.appear_then_click(button)


class HeroTestSkillFallbackTests(unittest.TestCase):
    def setUp(self):
        timer_patch = patch('tasks.HeroTest.script_task.Timer')
        timer = timer_patch.start()
        self.addCleanup(timer_patch.stop)
        # Allow one normal recognition attempt, then keep reporting a timeout.
        self.expired = timer.return_value.start.return_value.reached_and_reset

    def run_selection(self, task, method):
        self.expired.side_effect = itertools.chain([False], itertools.repeat(True))
        return getattr(task, method)()

    def assert_fallback_then_confirm(self, task, method):
        self.assertTrue(self.run_selection(task, method))
        self.assertEqual([event for event, _ in task.events], ['fallback', 'confirm'])
        self.assertIsInstance(task.events[0][1], RuleClick)
        self.assertEqual(task.frames, 2)

    def test_hero1_unrecognized_skills_fall_back_then_confirm(self):
        self.assert_fallback_then_confirm(ScriptedHeroTest(), 'hero1_skill_wait')

    def test_hero2_unrecognized_skills_fall_back_then_confirm(self):
        self.assert_fallback_then_confirm(ScriptedHeroTest(), 'hero2_skill_wait')

    def test_empty_hero2_pvp_priority_list_does_not_retry_forever(self):
        task = ScriptedHeroTest(mode=SkillMode.PVP)
        self.assert_fallback_then_confirm(task, 'hero2_skill_wait')

    def test_hero1_recognized_skills_keep_their_priority(self):
        task = ScriptedHeroTest()
        task.visible_skills = [task.I_BCMJ_SKILL_ADD2, task.I_BCMJ_BLESS]
        self.assertTrue(self.run_selection(task, 'hero1_skill_wait'))
        self.assertEqual([event for event, _ in task.events], ['preferred', 'confirm'])
        self.assertIs(task.events[0][1], task.I_BCMJ_SKILL_ADD2)
        self.assertEqual(len(task.attempted_skills), 2)
        self.assertEqual(task.frames, 1)

    def test_hero2_recognized_skills_keep_their_priority(self):
        task = ScriptedHeroTest()
        task.visible_skills = [task.I_HERO2_SKILL2, task.I_HERO2_SKILL3]
        self.assertTrue(self.run_selection(task, 'hero2_skill_wait'))
        self.assertEqual([event for event, _ in task.events], ['preferred', 'confirm'])
        self.assertIs(task.events[0][1], task.I_HERO2_SKILL2)
        self.assertEqual(len(task.attempted_skills), 2)
        self.assertEqual(task.frames, 1)

    def test_no_panel_does_not_click(self):
        for method in ('hero1_skill_wait', 'hero2_skill_wait'):
            with self.subTest(method=method):
                task = ScriptedHeroTest(panel_visible=False)
                self.assertFalse(self.run_selection(task, method))
                self.assertEqual(task.events, [])
                self.assertEqual(task.frames, 0)

    def test_panel_closed_at_timeout_does_not_click_randomly(self):
        for method in ('hero1_skill_wait', 'hero2_skill_wait'):
            with self.subTest(method=method):
                task = ScriptedHeroTest(close_on_frame=2)
                self.run_selection(task, method)
                self.assertEqual(task.events, [])
                self.assertEqual(task.frames, 2)


if __name__ == '__main__':
    unittest.main()
