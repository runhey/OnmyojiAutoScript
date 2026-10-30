"""Offline flow regressions; no Config, Device or game connection is created."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from module.exception import ScriptError
from tasks.WantedQuests.script_task import ScriptTask
from tasks.WantedQuests.config import CooperationType


class ShortTimer:
    def __init__(self, *args, **kwargs):
        self.ticks = 0
    def start(self):
        return self
    def reached(self):
        self.ticks += 1
        return self.ticks > 4


class WantedUiTests(unittest.TestCase):
    def setUp(self):
        self.task = object.__new__(ScriptTask)
        self.task.device = SimpleNamespace(image=None, click=Mock())
        self.task.screenshot = Mock()
        self.task.click = Mock(return_value=True)
        self.task.appear = Mock(return_value=False)
        self.task.appear_then_click = Mock(return_value=True)
        self.task.goto_page = Mock(side_effect=AssertionError('Unexpected courtyard detour'))
        self.timer = patch('tasks.WantedQuests.script_task.Timer', ShortTimer)
        self.timer.start()
        self.addCleanup(self.timer.stop)

    def test_direct_exploration_click_and_destination_check(self):
        t = self.task
        t.wanted_board_open = Mock(return_value=True)
        t.appear.side_effect = [False, True]
        self.assertTrue(t.goto_wanted_exploration())
        t.appear_then_click.assert_called_once_with(t.I_WQ_GOTO_EXPLORATION, interval=1)
        t.goto_page.assert_not_called()

    def test_direct_exploration_timeout_does_not_return_success(self):
        self.task.wanted_board_open = Mock(return_value=True)
        with self.assertRaises(ScriptError):
            self.task.goto_wanted_exploration()

    def test_submit_requires_actual_specialized_button_click(self):
        t = self.task
        t.appear.side_effect = [True, False]
        t.wanted_board_open = Mock(return_value=True)
        self.assertTrue(t.submit_wanted_invitation())
        t.appear_then_click.assert_called_once_with(t.I_WQ_INVITE_ENSURE, interval=1)

    def test_missing_submit_button_is_not_success(self):
        self.task.wanted_board_open = Mock(return_value=True)
        with self.assertRaises(ScriptError):
            self.task.submit_wanted_invitation()
        self.task.appear_then_click.assert_not_called()

    def test_submit_requires_dialog_to_close(self):
        self.task.appear.return_value = True
        with self.assertRaises(ScriptError):
            self.task.submit_wanted_invitation()

    @patch('tasks.WantedQuests.script_task.sleep')
    def test_random_invite_submits_after_five_selections(self, _sleep):
        t = self.task
        t.appear.return_value = True
        t.ui_click = Mock()
        t.submit_wanted_invitation = Mock(return_value=True)
        self.assertTrue(t.invite_random(t.I_WQ_INVITE_1))
        self.assertEqual(t.click.call_count, 5)
        t.submit_wanted_invitation.assert_called_once()

    @patch('tasks.WantedQuests.script_task.sleep')
    def test_random_no_selection_cancels_without_submission(self, _sleep):
        t = self.task
        t.appear.side_effect = [True, False]
        t.ui_click = Mock()
        t.ui_click_until_disappear = Mock()
        t.submit_wanted_invitation = Mock()
        self.assertFalse(t.invite_random(t.I_WQ_INVITE_1))
        t.submit_wanted_invitation.assert_not_called()
        t.ui_click_until_disappear.assert_called_once_with(t.I_WQ_INVITE_CANCEL)

    def test_named_friend_invite_submits(self):
        t = self.task
        t.ui_click = Mock()
        t.wait_until_appear = Mock()
        t.ocr_appear_click = Mock(side_effect=[True, False])
        t.appear.return_value = True
        t.submit_wanted_invitation = Mock(return_value=True)
        self.assertTrue(t.cooperation_invite(t.I_WQ_INVITE_1, 'test-friend'))
        t.submit_wanted_invitation.assert_called_once()

    def test_cooperation_can_be_in_fourth_card_without_first_card(self):
        t = self.task
        allowed = {str(t.I_WQ_INVITE_4), str(t.I_WQ_COOPERATION_TYPE_SUSHI_4)}
        t.appear.side_effect = lambda rule: str(rule) in allowed
        result = t.get_cooperation_info()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], CooperationType.Sushi)
        self.assertIs(result[0]['inviteBtn'], t.I_WQ_INVITE_4)

    def test_normal_mode_uses_direct_navigation(self):
        t = self.task
        t.open_wanted_board = Mock(return_value=True)
        t.wanted_board_open = Mock(return_value=True)
        t.appear.side_effect = lambda rule: rule is t.I_TRACE_DISABLE
        t.goto_wanted_exploration = Mock(return_value=True)
        self.assertTrue(t.pre_work())
        t.goto_wanted_exploration.assert_called_once()
        t.goto_page.assert_not_called()

    def test_cooperation_only_uses_direct_navigation(self):
        t = self.task
        t.open_wanted_board = Mock(return_value=True)
        t.appear.side_effect = lambda rule: rule is t.I_WQ_INVITE_1
        t.all_cooperation_invite = Mock(return_value=[{'inviteResult': True}])
        t.goto_wanted_exploration = Mock(return_value=True)
        self.assertTrue(t.pre_work_cooperation_only())
        t.goto_wanted_exploration.assert_called_once()

    def test_no_cooperation_does_not_iterate_boolean_result(self):
        t = self.task
        t.get_cooperation_info = Mock(return_value=[])
        self.assertEqual(t.all_cooperation_invite(), [])

    def test_detail_tracking_clicks_only_after_details_open(self):
        t = self.task
        t.appear.side_effect = lambda rule: rule in (t.I_WQ_INVITE_1, t.I_WQ_TRACE_ONE_CHECK_OPENED, t.I_WQ_TRACE_ONE_ENABLE)
        t.close_wanted_detail = Mock()
        self.assertTrue(t.trace_one(t.I_WQ_INVITE_1))
        t.close_wanted_detail.assert_called_once()
        t.device.click.assert_not_called()


    def test_source_labels_and_variable_width_destination_regions(self):
        t = self.task
        settings = SimpleNamespace(layer_limit=SimpleNamespace(value='无限制'),
                                   battle_priority='探索>挑战>秘闻')
        t.config = SimpleNamespace(model=SimpleNamespace(wanted_quests=SimpleNamespace(
            wanted_quests_config=settings)))
        t.explore, t.challenge, t.secret = Mock(), Mock(), Mock()
        t.untrack_current_wanted = Mock()
        t.unwanted_boss_name_list, t.want_strategy_excluding = [], []
        t.O_WQ_MONSTER_TYPE = SimpleNamespace(detect_text=Mock(return_value='自己击败天邪鬼绿'))
        t.appear.side_effect = lambda rule: rule in (t.I_WQ_TRACE_ONE_CHECK_OPENED, t.I_GOTO_1)
        texts = {'wq_type_1': '式神碎片', 'wq_info_1': '第一章(数量：14）',
                 'wq_type_2': '探索第六', 'wq_info_2': '第六章(数量：9）',
                 'wq_type_3': '妖气', 'wq_type_4': ''}
        def recognize(rule, _image):
            if rule.name.lower() == 'wq_info_1':
                self.assertEqual(rule.roi[0], 757)
            if rule.name.lower() == 'wq_info_2':
                self.assertEqual(rule.roi[0], 713)
            return texts[rule.name.lower()]
        with patch('module.atom.ocr.RuleOcr.ocr', recognize):
            t.execute_mission(t.O_WQ_TEXT_ALL, 6, 1)
            t.explore.assert_called_once_with(t.I_GOTO_2, 1)
            settings.battle_priority = '挑战>探索>秘闻'
            t.execute_mission(t.O_WQ_TEXT_ALL, 6, 1)
            t.challenge.assert_called_once_with(t.I_GOTO_1, 1)
        t.untrack_current_wanted.assert_not_called()

    def test_board_is_not_accepted_behind_details_or_friend_dialog(self):
        t = self.task
        for overlay in (t.I_WQ_TRACE_ONE_CHECK_OPENED, t.I_WQ_INVITE_ENSURE):
            t.appear.side_effect = lambda rule: rule in (overlay, t.I_TRACE_DISABLE)
            self.assertFalse(t.wanted_board_open())


if __name__ == '__main__':
    unittest.main()
