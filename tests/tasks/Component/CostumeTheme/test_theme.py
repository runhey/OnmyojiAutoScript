"""Offline regression tests; no device or game interaction."""
import unittest
from copy import deepcopy

from tasks.Component.Costume.config import CostumeConfig, ThemeType
from tasks.Component.Costume.costume_base import CostumeBase
from tasks.Component.CostumeTheme.theme import apply_theme, _THEME_NAMES
from tasks.GameUi.assets import GameUiAssets


class ThemeTests(unittest.TestCase):
    def setUp(self):
        apply_theme(ThemeType.COSTUME_THEME_DEFAULT)

    def tearDown(self):
        apply_theme(ThemeType.COSTUME_THEME_DEFAULT)

    def test_enum_schema_and_default(self):
        self.assertEqual(CostumeConfig().costume_theme_type, ThemeType.COSTUME_THEME_DEFAULT)
        self.assertEqual(CostumeConfig(costume_theme_type='costume_theme_1').costume_theme_type,
                         ThemeType.COSTUME_THEME_1)
        schema = CostumeConfig.model_json_schema()
        self.assertIn('costume_theme_1', schema['$defs']['ThemeType']['enum'])

    def test_shared_references_are_updated_and_default_restores(self):
        refs = {name: getattr(GameUiAssets, name) for name in _THEME_NAMES}
        defaults = {name: (rule.file, tuple(rule.roi_front), rule.roi_back) for name, rule in refs.items()}
        for rule in refs.values():
            _ = rule.image  # Prime old image cache before changing theme.
            _ = rule.name
        CostumeBase().check_costume_theme(ThemeType.COSTUME_THEME_1)
        for name, rule in refs.items():
            self.assertIs(rule, getattr(GameUiAssets, name))
            self.assertIn('/CostumeTheme/', rule.file)
            self.assertIsNone(rule._image)
            self.assertNotIn('name', rule.__dict__)
            self.assertEqual(rule.image.shape[:2], (rule.roi_front[3], rule.roi_front[2]))
        CostumeBase().check_costume_theme(ThemeType.COSTUME_THEME_DEFAULT)
        for name, rule in refs.items():
            self.assertEqual((rule.file, tuple(rule.roi_front), rule.roi_back), defaults[name])
            self.assertIsNone(rule._image)

    def test_reapply_resets_match_position_without_mutating_source(self):
        apply_theme(ThemeType.COSTUME_THEME_1)
        rule = GameUiAssets.I_MAIN_GOTO_TEAM
        original = tuple(rule.roi_front)
        rule.roi_front[0] = 0
        apply_theme(ThemeType.COSTUME_THEME_1)
        self.assertEqual(tuple(rule.roi_front), original)

    def test_invalid_theme_does_not_mutate_rules(self):
        rule = GameUiAssets.I_MAIN_GOTO_TEAM
        original = deepcopy(rule.__dict__)
        with self.assertRaises(KeyError):
            apply_theme('not_a_theme')
        self.assertEqual(rule.__dict__, original)


if __name__ == '__main__':
    unittest.main()
