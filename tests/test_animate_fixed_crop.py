"""Regression coverage for animation matching with desktop ROI padding."""

import unittest
from unittest.mock import patch

import numpy as np

from module.atom.animate import RuleAnimate
from module.atom.click import RuleClick
from module.atom.image import RuleImage


class AnimationCropTests(unittest.TestCase):
    def setUp(self):
        self.image = np.random.default_rng(42).integers(
            0, 256, (720, 1280, 3), dtype=np.uint8)

    def test_repeated_stability_with_and_without_refresh(self):
        for pad in (0, 2):
            for roi in ((1213, 79, 66, 265), (300, 200, 80, 60)):
                for refresh in (False, True):
                    with self.subTest(pad=pad, roi=roi, refresh=refresh), \
                            patch("module.atom.image.ROI_MATCH_PAD", pad):
                        rule = RuleImage(roi, roi, "Template matching", 0.8, "test.png")
                        animation = RuleAnimate(rule)
                        results = [
                            animation.stable(self.image, refresh_after_stable=refresh)
                            for _ in range(8)
                        ]
                        expected = [False, True] * 4 if refresh else [False] + [True] * 7
                        self.assertEqual(results, expected)

    def test_changed_frame_must_settle_again(self):
        changed = np.random.default_rng(43).integers(
            0, 256, self.image.shape, dtype=np.uint8)
        for pad in (0, 2):
            with self.subTest(pad=pad), patch("module.atom.image.ROI_MATCH_PAD", pad):
                roi = (1213, 79, 66, 265)
                animation = RuleAnimate(RuleClick(roi, roi, name="edge"))
                results = [animation.stable(frame) for frame in
                           (self.image, self.image, changed, changed, changed)]
                self.assertEqual(results, [False, True, False, True, True])

    def test_front_crop_and_search_region_can_differ(self):
        with patch("module.atom.image.ROI_MATCH_PAD", 2):
            animation = RuleAnimate(RuleClick(
                (300, 200, 80, 60), (280, 180, 120, 100), name="wide_search"))
            self.assertFalse(animation.stable(self.image))
            for _ in range(5):
                self.assertTrue(animation.stable(self.image))


if __name__ == "__main__":
    unittest.main()
