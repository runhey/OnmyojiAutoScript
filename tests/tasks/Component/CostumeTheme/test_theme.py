"""Offline regression tests; no device or game interaction."""
import unittest
from unittest.mock import patch
from module.server.i18n import I18n
import json
from pathlib import Path
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
        self.assertEqual(CostumeConfig(costume_theme_type='costume_theme_xinyu_mingxiao').costume_theme_type,
                         ThemeType.COSTUME_THEME_XINYU_MINGXIAO)
        schema = CostumeConfig.model_json_schema()
        self.assertIn('costume_theme_xinyu_mingxiao', schema['$defs']['ThemeType']['enum'])

    def test_shared_references_are_updated_and_default_restores(self):
        refs = {name: getattr(GameUiAssets, name) for name in _THEME_NAMES}
        defaults = {name: (rule.file, tuple(rule.roi_front), rule.roi_back) for name, rule in refs.items()}
        for rule in refs.values():
            _ = rule.image  # Prime old image cache before changing theme.
            _ = rule.name
        CostumeBase().check_costume_theme(ThemeType.COSTUME_THEME_XINYU_MINGXIAO)
        for name, rule in refs.items():
            self.assertIs(rule, getattr(GameUiAssets, name))
            if name == 'I_MAIN_SCROLL_CLOSE':
                self.assertIn('/CostumeTheme/theme2/', rule.file)
            else:
                self.assertEqual((rule.file, tuple(rule.roi_front), rule.roi_back), defaults[name])
            self.assertIsNone(rule._image)
            self.assertNotIn('name', rule.__dict__)
            self.assertEqual(rule.image.shape[:2], (rule.roi_front[3], rule.roi_front[2]))
        CostumeBase().check_costume_theme(ThemeType.COSTUME_THEME_DEFAULT)
        for name, rule in refs.items():
            self.assertEqual((rule.file, tuple(rule.roi_front), rule.roi_back), defaults[name])
            self.assertIsNone(rule._image)

    def test_reapply_resets_match_position_without_mutating_source(self):
        apply_theme(ThemeType.COSTUME_THEME_XINYU_MINGXIAO)
        rule = GameUiAssets.I_MAIN_SCROLL_CLOSE
        original = tuple(rule.roi_front)
        rule.roi_front[0] = 0
        apply_theme(ThemeType.COSTUME_THEME_XINYU_MINGXIAO)
        self.assertEqual(tuple(rule.roi_front), original)

    def test_only_scroll_has_theme_specific_material(self):
        from tasks.Component.CostumeTheme.assets import CostumeThemeAssets
        folder = Path(__file__).resolve().parents[4] / 'tasks/Component/CostumeTheme/theme2'
        items = json.loads((folder / 'image.json').read_text(encoding='utf-8'))
        self.assertEqual([item['itemName'] for item in items], ['main_scroll_close_2'])
        self.assertEqual({p.name for p in folder.glob('*.png')},
                         {'theme2_main_scroll_close_2.png'})
        self.assertEqual({name for name in vars(CostumeThemeAssets) if name.startswith('I_')},
                         {'I_MAIN_SCROLL_CLOSE_2'})

    def test_previous_local_selections_are_preserved(self):
        for value in ('costume_theme_1', 'costume_theme_2'):
            config = CostumeConfig(costume_theme_type=value)
            self.assertEqual(config.costume_theme_type, ThemeType.COSTUME_THEME_XINYU_MINGXIAO)
            self.assertEqual(config.model_dump(mode='json')['costume_theme_type'],
                             'costume_theme_xinyu_mingxiao')

    def test_theme_log_uses_supplementary_label_before_ui_translation_update(self):
        theme = ThemeType.COSTUME_THEME_XINYU_MINGXIAO
        with patch.object(I18n, 'load_additions', return_value={
                'zh-CN': {theme.value: '新语明霄'}}), \
             patch.object(I18n, 'trans_zh_cn', return_value=theme.value) as fallback, \
             patch('tasks.Component.Costume.costume_base.logger') as log:
            CostumeBase().check_costume_theme(theme)
        fallback.assert_not_called()
        log.info.assert_called_once_with(f'Switch menu theme {theme} (新语明霄)')

    def test_theme_log_falls_back_when_supplementary_label_is_missing(self):
        theme = ThemeType.COSTUME_THEME_XINYU_MINGXIAO
        with patch.object(I18n, 'load_additions', return_value={}), \
             patch.object(I18n, 'trans_zh_cn', return_value='已有运行时翻译') as fallback, \
             patch('tasks.Component.Costume.costume_base.logger') as log:
            CostumeBase().check_costume_theme(theme)
        fallback.assert_called_once_with(theme)
        log.info.assert_called_once_with(f'Switch menu theme {theme} (已有运行时翻译)')

    def test_invalid_theme_does_not_mutate_rules(self):
        for selected in (ThemeType.COSTUME_THEME_DEFAULT, ThemeType.COSTUME_THEME_XINYU_MINGXIAO):
            with self.subTest(selected=selected):
                apply_theme(selected)
                refs = {name: getattr(GameUiAssets, name) for name in _THEME_NAMES}
                states = {name: deepcopy(rule.__dict__) for name, rule in refs.items()}
                with self.assertRaises(KeyError):
                    apply_theme('not_a_theme')
                for name, ref in refs.items():
                    with self.subTest(rule=name):
                        self.assertIs(getattr(GameUiAssets, name), ref)
                        self.assertEqual(ref.__dict__, states[name])


if __name__ == '__main__':
    unittest.main()
