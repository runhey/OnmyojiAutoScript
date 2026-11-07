"""Check MetaDemon strategy inputs without a device or running game."""

import unittest
from unittest.mock import patch

from tasks.MetaDemon.config import Strategy


class MetaDemonStrategyTests(unittest.TestCase):
    def setUp(self):
        logger_patch = patch('tasks.MetaDemon.config.logger')
        logger_patch.start()
        self.addCleanup(logger_patch.stop)

    def test_accepts_supported_groups_and_teams(self):
        for group in range(1, 8):
            for team in range(1, 5):
                with self.subTest(group=group, team=team):
                    self.assertEqual(
                        Strategy.parse_group_team(f'{group},{team}'),
                        [group, team],
                    )

    def test_accepts_chinese_comma_and_spaces(self):
        self.assertEqual(Strategy.parse_group_team(' 7， 4 '), [7, 4])

    def test_rejects_unsupported_teams_with_range(self):
        for team in (0, 5, 6):
            with self.subTest(team=team):
                with self.assertRaisesRegex(ValueError, r'team must be in \[1-4\]'):
                    Strategy.parse_group_team(f'1,{team}')

    def test_rejects_team_five_in_either_strategy_field(self):
        for field in ('md_preset_group_team_1', 'md_preset_group_team_2'):
            with self.subTest(field=field):
                strategy = Strategy(**{field: '1,5'})
                with self.assertRaisesRegex(ValueError, r'team must be in \[1-4\]'):
                    Strategy.parse_all([strategy])


if __name__ == '__main__':
    unittest.main()
