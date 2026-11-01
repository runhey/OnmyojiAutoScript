"""Offline tests for the shared courtyard guild entrance (no device required).

Fixtures contain only the 120x100 guild search area at (495,590), cropped from
user-provided new-theme open/closed screenshots after 1280x720 normalization.
The original-template and altered-background cases are synthetic controls,
not real screenshots of the default theme.
"""
import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

import cv2
import numpy as np

from module.atom.image import RuleImage, set_roi_match_padding
from tasks.GameUi.assets import GameUiAssets
from tasks.Component.Costume.config import ThemeType
from tasks.Component.CostumeTheme.theme import apply_theme

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / 'fixtures'
OTHER_ENTRANCES = ('COLLECTION', 'TRAVEL', 'TEAM', 'MALL', 'DAILY', 'FRIENDS',
                   'ONMYODO', 'SHIKIGAMI_RECORDS')


class SharedGuildMaskTests(unittest.TestCase):
    def setUp(self):
        apply_theme(ThemeType.COSTUME_THEME_DEFAULT)
        set_roi_match_padding(0)

    def tearDown(self):
        apply_theme(ThemeType.COSTUME_THEME_DEFAULT)
        set_roi_match_padding(0)

    def rule(self, method='Masked template matching'):
        source = GameUiAssets.I_MAIN_GOTO_GUILD
        return RuleImage(tuple(source.roi_front), source.roi_back, method,
                         source.threshold, source.file)

    def frame(self, state):
        crop = cv2.cvtColor(cv2.imread(str(FIXTURES / ('guild_search_' + state + '.png'))),
                            cv2.COLOR_BGR2RGB)
        frame = np.full((720, 1280, 3), 100, dtype=np.uint8)
        frame[590:690, 495:615] = crop
        return frame

    def test_shared_source_and_mask_contract(self):
        items = json.loads((ROOT / 'tasks/GameUi/page/image_main.json').read_text(encoding='utf-8'))
        item = next(x for x in items if x['itemName'] == 'main_goto_guild')
        rule = self.rule()
        self.assertEqual(item['method'], 'Masked template matching')
        self.assertEqual(GameUiAssets.I_MAIN_GOTO_GUILD.method, item['method'])
        self.assertEqual(rule.threshold, 0.7)
        self.assertEqual(rule.roi_back, (495, 590, 120, 100))
        self.assertEqual(rule.mask.shape, rule.image.shape[:2])
        self.assertEqual(set(np.unique(rule.mask)), {0, 255})
        self.assertGreater(np.count_nonzero(rule.mask), 200)
        self.assertLess(np.count_nonzero(rule.mask), rule.mask.size)
        self.assertEqual(hashlib.sha256((ROOT / rule.file.removeprefix('./')).read_bytes()).hexdigest(),
                         'b7cbc4f76c6eef129e955b9b3d89a376a721b9930e4295011e98363bdd80a5d9')

    def test_new_theme_open_hits_at_guild_not_another_icon(self):
        for pad in (0, 2):
            with self.subTest(padding=pad):
                set_roi_match_padding(pad)
                rule = self.rule()
                self.assertTrue(rule.match(self.frame('open')))
                self.assertGreater(rule.last_score, 0.9)
                self.assertEqual(rule.roi_front[:2], [556, 610])

    def test_plain_matching_reproduces_reported_failure(self):
        rule = self.rule('Template matching')
        self.assertFalse(rule.match(self.frame('open')))
        self.assertAlmostEqual(rule.last_score, 0.52842, places=4)

    def test_closed_scroll_is_not_a_guild_entrance(self):
        for pad in (0, 2):
            with self.subTest(padding=pad):
                set_roi_match_padding(pad)
                rule = self.rule()
                self.assertFalse(rule.match(self.frame('closed')))
                self.assertLess(rule.last_score, rule.threshold)

    def test_original_template_synthetic_control(self):
        rule = self.rule()
        frame = np.full((720, 1280, 3), 100, dtype=np.uint8)
        frame[610:632, 556:606] = rule.image
        self.assertTrue(rule.match(frame))
        self.assertGreater(rule.last_score, 0.999)
        self.assertEqual(rule.roi_front[:2], [556, 610])

    def test_ignored_background_changes_do_not_change_result(self):
        rng = np.random.default_rng(1862)
        for variant in ('black', 'white', 'noise'):
            with self.subTest(background=variant):
                rule = self.rule()
                icon = rule.image.copy()
                background = (rng.integers(0, 256, icon.shape, dtype=np.uint8)
                              if variant == 'noise' else
                              np.full_like(icon, 0 if variant == 'black' else 255))
                icon[rule.mask == 0] = background[rule.mask == 0]
                frame = np.full((720, 1280, 3), 100, dtype=np.uint8)
                frame[610:632, 556:606] = icon
                self.assertTrue(rule.match(frame))
                self.assertGreater(rule.last_score, 0.999)
                self.assertEqual(rule.roi_front[:2], [556, 610])

    def test_other_entrance_icons_do_not_match_guild(self):
        for name in OTHER_ENTRANCES:
            with self.subTest(icon=name):
                rule = self.rule()
                icon = deepcopy(getattr(GameUiAssets, 'I_MAIN_GOTO_' + name)).image
                h, w = icon.shape[:2]
                frame = np.full((720, 1280, 3), 100, dtype=np.uint8)
                frame[610:610+h, 535:535+w] = icon
                self.assertFalse(rule.match(frame))

    def test_theme_switch_keeps_shared_mask_and_navigation_reference(self):
        from tasks.GameUi.default_pages import page_main
        ref = GameUiAssets.I_MAIN_GOTO_GUILD
        transitions = [t for t in page_main.transitions if t.action is ref]
        self.assertTrue(transitions)
        for theme in (ThemeType.COSTUME_THEME_XINYU_MINGXIAO, ThemeType.COSTUME_THEME_DEFAULT):
            apply_theme(theme)
            self.assertIs(GameUiAssets.I_MAIN_GOTO_GUILD, ref)
            self.assertEqual(ref.method, 'Masked template matching')
            self.assertIsNotNone(ref.mask)
            self.assertTrue(all(t.action is ref for t in transitions))
            self.assertTrue(ref.match(self.frame('open')))


if __name__ == '__main__':
    unittest.main()
