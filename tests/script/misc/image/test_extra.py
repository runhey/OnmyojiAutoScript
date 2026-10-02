"""
Tests for script.misc.image.extra

Adaptation layer holding the image helpers that exist only in OAS and have no
alasio/base/image counterpart. Alasio has no reference tests for them, so the
expectations here come from the formulas in each docstring.
"""
import numpy as np
import pytest

from script.misc.image.extra import (
    color_bar_percentage,
    color_mapping,
    image_left_strip,
    red_overlay_transparency,
    rgb2yuv,
)

# ==============================================================================
# rgb2yuv
# ==============================================================================


class TestRgb2Yuv:
    def test_shape_is_unchanged(self):
        assert rgb2yuv(np.zeros((4, 6, 3), np.uint8)).shape == (4, 6, 3)

    def test_black_maps_to_zero_luma_with_neutral_chroma(self):
        out = rgb2yuv(np.zeros((1, 1, 3), np.uint8))
        assert tuple(out[0, 0]) == (0, 128, 128)

    def test_white_maps_to_full_luma_with_neutral_chroma(self):
        out = rgb2yuv(np.full((1, 1, 3), 255, np.uint8))
        assert tuple(out[0, 0]) == (255, 128, 128)

    def test_pure_red_luma_is_the_rec601_weight(self):
        # Y = 0.299 * 255 = 76.245 -> 76
        out = rgb2yuv(np.array([[[255, 0, 0]]], np.uint8))
        assert tuple(out[0, 0]) == (76, 91, 255)

    def test_grey_has_equal_chroma(self):
        out = rgb2yuv(np.full((1, 1, 3), 128, np.uint8))[0, 0]
        assert out[0] == pytest.approx(128, abs=2)
        assert out[1] == pytest.approx(128, abs=2)


# ==============================================================================
# color_mapping
# ==============================================================================


@pytest.mark.filterwarnings("ignore:divide by zero:RuntimeWarning")
class TestColorMapping:
    def test_minimum_becomes_zero_and_maximum_becomes_255(self):
        image = np.array([[[0, 128, 255]]], np.uint8)
        out = color_mapping(image)
        assert out[0, 0, 0] == 0
        assert out[0, 0, 2] == 255

    def test_output_is_uint8(self):
        assert color_mapping(np.full((4, 4, 3), 90, np.uint8)).dtype == np.uint8

    def test_constant_image_collapses_to_a_single_mid_value(self):
        # high == low makes the multiplier blow up, the cap clamps it to the
        # default max_multiply and every pixel lands on the same value.
        # NOTE: emits a numpy divide-by-zero RuntimeWarning on the way.
        with np.errstate(divide="ignore"):
            out = color_mapping(np.full((2, 2, 3), 90, np.uint8))
        assert set(np.unique(out)) == {127}

    def test_result_stays_in_range(self):
        image = np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3)
        out = color_mapping(image)
        assert out.min() >= 0
        assert out.max() <= 255

    def test_max_multiply_limits_the_contrast(self):
        image = np.array([[[0, 10, 20]]], np.uint8)
        # multiply = min(255 / 20, max_multiply); a small cap keeps the top
        # below 255 and adds an offset instead
        assert color_mapping(image, max_multiply=1)[0, 0, 2] < 255

    def test_handles_grayscale_input(self):
        assert color_mapping(np.arange(24, dtype=np.uint8).reshape(4, 6)).shape == (4, 6)


# ==============================================================================
# color_bar_percentage
# ==============================================================================


class TestColorBarPercentage:
    def _bar(self, width=200, left=20, right=150, color=(128, 64, 200)):
        image = np.zeros((40, width, 3), np.uint8)
        image[:, left:right] = color
        return image

    def test_measures_the_filled_fraction(self):
        # 130 of 200 columns are painted
        result = color_bar_percentage(self._bar(), (0, 0, 200, 40), (128, 64, 200))
        assert result == 0.745

    def test_reverse_reads_the_bar_from_the_other_end(self):
        image = self._bar()
        forward = color_bar_percentage(image, (0, 0, 200, 40), (128, 64, 200))
        reverse = color_bar_percentage(image, (0, 0, 200, 40), (128, 64, 200), reverse=True)
        assert forward != reverse

    def test_empty_bar_returns_the_starter_position(self):
        image = np.zeros((40, 200, 3), np.uint8)
        assert color_bar_percentage(image, (0, 0, 200, 40), (128, 64, 200), starter=25) == 25 / 200

    def test_fully_filled_bar_stops_one_column_short(self):
        # the scan returns the last matching index, so a 200 column bar tops
        # out at 199 / 200
        image = np.full((40, 200, 3), (128, 64, 200), np.uint8)
        assert color_bar_percentage(image, (0, 0, 200, 40), (128, 64, 200)) == 0.995

    def test_result_is_always_a_fraction(self):
        for width in (100, 200, 333):
            image = self._bar(width=width, left=10, right=width - 30)
            result = color_bar_percentage(image, (0, 0, width, 40), (128, 64, 200))
            assert 0.0 <= result <= 1.0


# ==============================================================================
# image_left_strip
# ==============================================================================


class TestImageLeftStrip:
    def test_strips_after_the_first_dark_column(self):
        image = np.full((40, 200), 255, np.uint8)
        image[:, 0:30] = 10
        assert image_left_strip(image, 128, 5).shape[1] == 195

    def test_finds_the_leftmost_dark_column_not_the_darkest(self):
        image = np.full((40, 200), 255, np.uint8)
        image[:, 10] = 0  # darkest
        image[:, 50] = 100  # also below the threshold, but further right
        # first match is column 10, so the strip starts at 10 + 5
        assert image_left_strip(image, 128, 5).shape[1] == 185

    def test_no_dark_column_leaves_the_image_alone(self):
        image = np.full((40, 200), 255, np.uint8)
        np.testing.assert_array_equal(image_left_strip(image, 128, 5), image)

    def test_length_zero_only_drops_the_leading_columns(self):
        image = np.full((40, 200), 255, np.uint8)
        image[:, 0:30] = 10
        assert image_left_strip(image, 128, 0).shape[1] == 200

    def test_strip_past_the_right_edge_is_a_noop(self):
        image = np.full((40, 200), 255, np.uint8)
        image[:, 0:30] = 10
        np.testing.assert_array_equal(image_left_strip(image, 128, 500), image)

    def test_height_is_preserved(self):
        image = np.full((17, 200), 255, np.uint8)
        image[:, 0:30] = 10
        assert image_left_strip(image, 128, 5).shape[0] == 17


# ==============================================================================
# red_overlay_transparency
# ==============================================================================


class TestRedOverlayTransparency:
    def test_matches_the_documented_ratio(self):
        # (200 - 100) / (247 - 100)
        assert red_overlay_transparency((100, 0, 0), (200, 0, 0)) == 100 / 147

    def test_unchanged_color_is_fully_transparent(self):
        assert red_overlay_transparency((100, 0, 0), (100, 0, 0)) == 0.0

    def test_full_overlay_is_opaque(self):
        assert red_overlay_transparency((100, 0, 0), (247, 0, 0)) == 1.0

    def test_halving_the_gap_halves_the_ratio(self):
        low = red_overlay_transparency((100, 0, 0), (150, 0, 0))
        high = red_overlay_transparency((100, 0, 0), (200, 0, 0))
        assert low == pytest.approx(high / 2, abs=1e-9)

    def test_red_anchor_is_configurable(self):
        assert red_overlay_transparency((100, 0, 0), (200, 0, 0), red=200) == 1.0