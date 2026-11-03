"""Offline regression tests for shared realm assets and distant carp banners."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from module.atom.image import RuleImage, set_roi_match_padding
from tasks.Component.Costume.config import CarpBannerType
from tasks.Component.Costume.costume_base import CostumeBase
from tasks.Component.CostumeCarpBanner.assets import CostumeCarpBannerAssets
from tasks.KekkaiUtilize.assets import KekkaiUtilizeAssets

ROOT = Path(__file__).resolve().parents[3]
TARGETS = {
    'I_SHI_GROWN': (599, 293, 45, 65),
    'I_SHI_CARD': (777, 288, 50, 72),
    'I_SHI_DEFENSE': (410, 288, 45, 80),
    'I_REALM_SHIN': (308, 300, 85, 85),
    'I_CARD_EXP': (770, 158, 70, 68),
    'I_BOX_AP': (880, 312, 65, 65),
    'I_BOX_EXP': (937, 312, 52, 70),
}
ORIGINAL_REGIONS = {
    'I_SHI_GROWN': (519, 212, 220, 281),
    'I_SHI_CARD': (823, 210, 252, 297),
    'I_SHI_DEFENSE': (178, 209, 261, 274),
    'I_REALM_SHIN': (22, 359, 393, 328),
    'I_CARD_EXP': (829, 33, 231, 257),
    'I_BOX_AP': (744, 336, 395, 216),
    'I_BOX_EXP': (792, 334, 359, 232),
}


class Probe(CostumeBase, KekkaiUtilizeAssets):
    """Only rule replacement is exercised; no Config or Device is created."""
    pass


def screenshot():
    fixture = Path(__file__).parent / 'fixtures/distant_realm_elements.png'
    crop = cv2.cvtColor(cv2.imdecode(np.fromfile(fixture, dtype=np.uint8), cv2.IMREAD_COLOR),
                       cv2.COLOR_BGR2RGB)
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[150:460, 300:1000] = crop
    return image


def configured_rules():
    probe = Probe()
    for name in TARGETS:
        setattr(probe, name, deepcopy(getattr(KekkaiUtilizeAssets, name)))
    with patch('tasks.Component.Costume.costume_base.I18n.trans_zh_cn', return_value='carp'):
        probe.check_costume_carpbanner(CarpBannerType.COSTUME_CARPBANNER_3)
    return {name: getattr(probe, name) for name in TARGETS}


class RealmMultiScaleTests(unittest.TestCase):
    def tearDown(self):
        set_roi_match_padding(0)

    def test_all_seven_visible_elements_match_at_correct_locations(self):
        for padding in (0, 2):
            set_roi_match_padding(padding)
            for name, rule in configured_rules().items():
                with self.subTest(padding=padding, name=name):
                    self.assertTrue(rule.match(screenshot(), threshold=0.6 if name == 'I_BOX_EXP' else None))
                    x, y, w, h = rule.roi_front
                    ex, ey, ew, eh = TARGETS[name]
                    self.assertTrue(ex <= x + w / 2 < ex + ew)
                    self.assertTrue(ey <= y + h / 2 < ey + eh)
                    self.assertEqual(rule.last_scale, None if name == 'I_BOX_EXP' else
                                     (0.6 if name.startswith('I_SHI_') else 1.0))

    def test_missing_target_is_not_accepted(self):
        for padding in (0, 2):
            set_roi_match_padding(padding)
            for name, rule in configured_rules().items():
                with self.subTest(padding=padding, name=name):
                    image = screenshot()
                    x, y, w, h = TARGETS[name]
                    image[y-5:y+h+5, x-5:x+w+5] = 0
                    self.assertFalse(rule.match(image, threshold=0.6 if name == 'I_BOX_EXP' else None), (name, rule.last_score, rule.roi_front))

    def test_empty_screen_has_no_matches(self):
        for name, rule in configured_rules().items():
            with self.subTest(name=name):
                self.assertFalse(rule.match(np.zeros((720, 1280, 3), dtype=np.uint8)))

    def test_cross_skin_search_regions(self):
        expected = {
            'I_SHI_DEFENSE': (260, 250, 210, 210),
            'I_SHI_GROWN': (560, 250, 130, 220),
            'I_SHI_CARD': (760, 250, 220, 220),
            'I_REALM_SHIN': (140, 270, 270, 285),
            'I_CARD_EXP': (750, 90, 250, 230),
            'I_BOX_AP': (790, 285, 295, 240),
            'I_BOX_EXP': (875, 285, 255, 240),
            'I_BOX_EXP_MAX': (875, 285, 255, 240),
            'I_UTILIZE_EXP': (500, 65, 220, 280),
        }
        for name, roi in expected.items():
            self.assertEqual(tuple(getattr(KekkaiUtilizeAssets, name).roi_back), roi)
            if name.startswith('I_SHI_'):
                for skin in range(1, 4):
                    self.assertEqual(tuple(getattr(CostumeCarpBannerAssets,
                                                  name + '_' + str(skin)).roi_back), roi)

    def test_collected_bottle_does_not_match_white_animals_at_task_threshold(self):
        fixture = Path(__file__).parent / 'fixtures/collected_bottle_animals.png'
        crop = cv2.cvtColor(cv2.imdecode(np.fromfile(fixture, dtype=np.uint8),
                                      cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        image[280:640, 790:1150] = crop
        for padding in (0, 2):
            set_roi_match_padding(padding)
            for name in ('I_BOX_EXP', 'I_BOX_EXP_MAX'):
                for roi in ((875, 285, 255, 240), (790, 480, 350, 150)):
                    rule = deepcopy(getattr(KekkaiUtilizeAssets, name))
                    rule.roi_back = roi
                    self.assertFalse(rule.match(image, threshold=0.6),
                                     (name, roi, rule.last_score))

    def test_bottle_click_dimensions_match_replacement_template(self):
        rule = deepcopy(KekkaiUtilizeAssets.I_BOX_EXP)
        height, width = rule.image.shape[:2]
        self.assertEqual(tuple(rule.roi_front[2:]), (width, height))
        self.assertTrue(rule.match(screenshot(), threshold=0.6))

    def test_runtime_rules_keep_original_templates_and_thresholds(self):
        defaults = {'I_REALM_SHIN': 0.9, 'I_CARD_EXP': 0.8,
                    'I_BOX_AP': 0.7, 'I_BOX_EXP': 0.7}
        for name, rule in configured_rules().items():
            with self.subTest(name=name):
                if name.startswith('I_SHI_'):
                    source = getattr(CostumeCarpBannerAssets, name + '_3')
                    self.assertEqual(rule.file, source.file)
                    self.assertEqual(rule.threshold, 0.5)
                else:
                    self.assertEqual(rule.file, getattr(KekkaiUtilizeAssets, name).file)
                    self.assertEqual(rule.threshold, defaults[name])
                self.assertEqual(rule.method, 'Template matching' if name == 'I_BOX_EXP'
                                 else 'Multi-scale template matching')

    def test_original_size_templates_remain_recognizable(self):
        for name, rule in configured_rules().items():
            with self.subTest(name=name):
                image = np.zeros((720, 1280, 3), dtype=np.uint8)
                x, y, _, _ = rule.roi_back
                template = rule.image
                h, w = template.shape[:2]
                image[y+10:y+10+h, x+10:x+10+w] = template
                self.assertTrue(rule.match(image))
                self.assertEqual(rule.last_scale, None if name == 'I_BOX_EXP' else 1.0)
                self.assertEqual(rule.roi_front, [x+10, y+10, w, h])

    def test_replacement_copies_method_and_clears_cached_dispatch(self):
        probe = Probe()
        probe.I_SHI_GROWN = deepcopy(KekkaiUtilizeAssets.I_SHI_GROWN)
        target = probe.I_SHI_GROWN
        self.assertTrue(target.is_template_match)
        self.assertFalse(target.is_multi_scale_template_match)
        _ = target.image
        source = CostumeCarpBannerAssets.I_SHI_GROWN_3
        probe.replace_img('I_SHI_GROWN', source)
        self.assertIs(probe.I_SHI_GROWN, target)
        self.assertIsNone(target._image)
        self.assertFalse(target.is_template_match)
        self.assertTrue(target.is_multi_scale_template_match)
        self.assertTrue(target.match(screenshot()))
        self.assertEqual(source.roi_front, [600, 277, 19, 34])
        self.assertIsNot(target.roi_front, source.roi_front)

    def test_replacement_can_return_to_original_matching_method(self):
        probe = Probe()
        probe.I_SHI_GROWN = deepcopy(KekkaiUtilizeAssets.I_SHI_GROWN)
        probe.replace_img('I_SHI_GROWN', CostumeCarpBannerAssets.I_SHI_GROWN_3)
        self.assertTrue(probe.I_SHI_GROWN.is_multi_scale_template_match)
        probe.replace_img('I_SHI_GROWN', KekkaiUtilizeAssets.I_SHI_GROWN)
        self.assertTrue(probe.I_SHI_GROWN.is_template_match)
        self.assertFalse(probe.I_SHI_GROWN.is_multi_scale_template_match)

    def test_replacement_can_preserve_fixed_search_region(self):
        probe = Probe()
        probe.I_SHI_GROWN = deepcopy(KekkaiUtilizeAssets.I_SHI_GROWN)
        original = probe.I_SHI_GROWN.roi_back
        probe.replace_img('I_SHI_GROWN', CostumeCarpBannerAssets.I_SHI_GROWN_3,
                          rp_roi_back=False)
        self.assertEqual(probe.I_SHI_GROWN.roi_back, original)

    def test_manual_realm_tool_references_existing_enum_members(self):
        import ast
        from tasks.Component.Costume.config import RealmType
        tool = ROOT / 'tasks/Component/Costume/costume_test_realm.py'
        tree = ast.parse(tool.read_text(encoding='utf-8'))
        members = [node.attr for node in ast.walk(tree)
                   if isinstance(node, ast.Attribute)
                   and isinstance(node.value, ast.Name)
                   and node.value.id == 'RealmType']
        self.assertTrue(members)
        for member in members:
            self.assertIn(member, RealmType.__members__)

    def test_generated_classes_match_json(self):
        for rel, assets in [('tasks/KekkaiUtilize/realm/image.json', KekkaiUtilizeAssets),
                            ('tasks/Component/CostumeCarpBanner/cb3/image.json',
                             CostumeCarpBannerAssets)]:
            for row in json.loads((ROOT / rel).read_text(encoding='utf-8')):
                with self.subTest(file=rel, name=row['itemName']):
                    rule = getattr(assets, 'I_' + row['itemName'].upper())
                    self.assertEqual(rule.method, row['method'])
                    self.assertEqual(tuple(rule.roi_back), tuple(map(int, row['roiBack'].split(','))))
                    self.assertEqual(rule.threshold, row['threshold'])


if __name__ == '__main__':
    unittest.main()
