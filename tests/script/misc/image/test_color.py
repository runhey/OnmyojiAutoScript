"""
Tests for script.misc.image.color

Verbatim copy of alasio/base/image/color.py, so Alasio has no reference tests
for it. Expectations here come from the documented formulas in the docstrings,
not from measuring this machine's cv2 build.
"""
import numpy as np
import pytest

from script.misc.image.color import (
    color_mask,
    color_similar,
    color_similar_1d,
    color_similarity,
    color_similarity_2d,
    extract_letters,
    extract_white_letters,
    get_color,
    rgb2gray,
    rgb2hsv,
    rgb2luma,
    rgb565_to_rgb888,
    rgbmax,
    rgbmin,
    rgbminmax,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def rgb():
    """
    2x2 RGB, every pixel a distinct known colour, and every max+min pair has an
    even sum so that rgb2gray's addWeighted(0.5, 0.5) is exact.

        pixel     r    g    b     max   min   (max+min)/2
        (0, 0)   10   20   30     30    10       20
        (0, 1)  200  100   50    200    50      125
        (1, 0)    0    0  254    254     0      127
        (1, 1)  255  255  255    255   255      255
    """
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    image[0, 0] = (10, 20, 30)
    image[0, 1] = (200, 100, 50)
    image[1, 0] = (0, 0, 254)
    image[1, 1] = (255, 255, 255)
    return image


# ==============================================================================
# rgbmax / rgbmin / rgbminmax
# ==============================================================================


class TestRgbExtremes:
    def test_rgbmax_is_per_pixel_channel_maximum(self, rgb):
        np.testing.assert_array_equal(rgbmax(rgb), np.array([[30, 200], [254, 255]], np.uint8))

    def test_rgbmin_is_per_pixel_channel_minimum(self, rgb):
        np.testing.assert_array_equal(rgbmin(rgb), np.array([[10, 50], [0, 255]], np.uint8))

    def test_rgbminmax_returns_minimum_first(self, rgb):
        minimum, maximum = rgbminmax(rgb)
        np.testing.assert_array_equal(minimum, rgbmin(rgb))
        np.testing.assert_array_equal(maximum, rgbmax(rgb))

    def test_output_is_two_dimensional_uint8(self, rgb):
        assert rgbmax(rgb).shape == (2, 2)
        assert rgbmax(rgb).dtype == np.uint8
        assert rgbmin(rgb).dtype == np.uint8
        assert rgbminmax(rgb)[0].dtype == np.uint8

    def test_three_channels_only(self):
        # cv2.split yields 4 planes for RGBA and the unpack would blow up
        rgba = np.full((2, 2, 4), 7, dtype=np.uint8)
        with pytest.raises(ValueError):
            rgbminmax(rgba)


# ==============================================================================
# rgb2gray
# ==============================================================================


class TestRgb2Gray:
    def test_formula_is_half_the_channel_range(self, rgb):
        expected = (rgbmax(rgb).astype(int) + rgbmin(rgb).astype(int)) // 2
        np.testing.assert_array_equal(rgb2gray(rgb), expected.astype(np.uint8))

    def test_exact_values(self, rgb):
        np.testing.assert_array_equal(rgb2gray(rgb), np.array([[20, 125], [127, 255]], np.uint8))

    def test_constant_image_maps_to_that_value(self):
        image = np.full((2, 2, 3), 77, dtype=np.uint8)
        np.testing.assert_array_equal(rgb2gray(image), np.full((2, 2), 77, np.uint8))

    def test_black_and_white_are_stable(self):
        for value in (0, 255):
            image = np.full((2, 2, 3), value, dtype=np.uint8)
            np.testing.assert_array_equal(rgb2gray(image), np.full((2, 2), value, np.uint8))


# ==============================================================================
# rgb2hsv
# ==============================================================================


class TestRgb2Hsv:
    def test_hue_scale_is_0_to_360_not_0_to_255(self):
        # cv2 stores hue as 0~179; the wrapper doubles it and rescales S/V to 0~100
        expected = {"red": 0.0, "green": 120.0, "blue": 240.0}
        for name, color in (
            ("red", (255, 0, 0)),
            ("green", (0, 255, 0)),
            ("blue", (0, 0, 255)),
        ):
            hue, _, _ = rgb2hsv(np.array([[color]], np.uint8))[0, 0]
            assert hue == pytest.approx(expected[name], abs=1e-6), name

    def test_saturated_primaries_have_saturation_100(self):
        for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
            _, saturation, value = rgb2hsv(np.array([[color]], np.uint8))[0, 0]
            assert saturation == pytest.approx(100, abs=1e-6)
            assert value == pytest.approx(100, abs=1e-6)

    def test_white_has_zero_saturation_and_full_value(self):
        _, saturation, value = rgb2hsv(np.array([[[255, 255, 255]]], np.uint8))[0, 0]
        assert saturation == pytest.approx(0, abs=1e-6)
        assert value == pytest.approx(100, abs=1e-6)

    def test_value_is_relative_luminance_in_percent(self):
        # 128 / 255 * 100
        _, _, value = rgb2hsv(np.array([[[128, 128, 128]]], np.uint8))[0, 0]
        assert value == pytest.approx(128 / 255 * 100, abs=1e-6)

    def test_runs_without_the_removed_numpy_float_alias(self, rgb):
        # the OAS original called np.float (removed in numpy 1.24) and raised
        # AttributeError; Alasio's version builds the output with the builtin
        assert rgb2hsv(rgb).dtype == np.dtype(float)


# ==============================================================================
# rgb2luma
# ==============================================================================


class TestRgb2Luma:
    def test_fast_path_is_within_one_of_the_exact_path(self):
        image = np.arange(3 * 4 * 3, dtype=np.uint8).reshape(3, 4, 3)
        fast = rgb2luma(image, fast=True).astype(int)
        exact = rgb2luma(image, fast=False).astype(int)
        # the docstring documents a +-1 difference from float weighting
        assert np.abs(fast - exact).max() <= 1

    def test_exact_path_of_a_grey_image_equals_the_input(self):
        grey = np.full((3, 4), 90, dtype=np.uint8)
        image = np.stack([grey] * 3, axis=2)
        np.testing.assert_array_equal(rgb2luma(image, fast=False), grey)

    def test_fast_path_also_preserves_grey(self):
        grey = np.full((3, 4), 90, dtype=np.uint8)
        image = np.stack([grey] * 3, axis=2)
        np.testing.assert_array_equal(rgb2luma(image, fast=True), grey)

    def test_black_and_white_are_stable_on_both_paths(self):
        for value in (0, 255):
            image = np.full((2, 2, 3), value, dtype=np.uint8)
            for fast in (True, False):
                np.testing.assert_array_equal(rgb2luma(image, fast=fast), np.full((2, 2), value, np.uint8))


# ==============================================================================
# rgb565_to_rgb888
# ==============================================================================


class TestRgb565ToRgb888:
    # Bit layout [ RRRRR (5) | GGGGGG (6) | BBBBB (5) ]
    # NOTE: exercised with a 1x2 array, not 1x1. On a (1, 1) input the three
    # `cv2.bitwise_and(image, <scalar>, dst=tmp)` calls silently fail to write
    # into tmp under opencv 5.0, so the result is uninitialised memory.
    @pytest.mark.parametrize(
        "packed, expected",
        [
            (0x0000, (0, 0, 0)),
            (0xF800, (255, 0, 0)),
            (0x07E0, (0, 255, 0)),
            (0x001F, (0, 0, 255)),
            (0xFFFF, (255, 255, 255)),
        ],
    )
    def test_primitives_round_trip(self, packed, expected):
        out = rgb565_to_rgb888(np.full((1, 2), packed, dtype=np.uint16))
        np.testing.assert_array_equal(out, np.array([[expected, expected]], np.uint8))

    def test_output_adds_a_channel(self):
        assert rgb565_to_rgb888(np.zeros((5, 7), dtype=np.uint16)).shape == (5, 7, 3)

    def test_zero_stays_zero(self):
        out = rgb565_to_rgb888(np.zeros((4, 4), dtype=np.uint16))
        assert not out.any()


# ==============================================================================
# get_color
# ==============================================================================


class TestGetColor:
    def test_area_is_optional_and_defaults_to_the_whole_image(self):
        image = np.full((4, 4, 3), (10, 20, 30), dtype=np.uint8)
        np.testing.assert_array_equal(get_color(image), np.array((10, 20, 30)))

    def test_area_restricts_to_the_region(self):
        image = np.full((4, 4, 3), (10, 20, 30), dtype=np.uint8)
        image[0, 0] = (255, 255, 255)
        # 2x2 region, one of four pixels is white
        np.testing.assert_allclose(get_color(image, (0, 0, 2, 2)), (71.25, 78.75, 86.25))

    def test_single_pixel_area(self):
        image = np.zeros((4, 4, 3), dtype=np.uint8)
        image[1, 1] = (255, 255, 255)
        np.testing.assert_allclose(get_color(image, (1, 1, 2, 2)), (255, 255, 255))

    def test_explicit_full_area_matches_omitted_area(self):
        image = np.arange(4 * 4 * 3, dtype=np.uint8).reshape(4, 4, 3)
        np.testing.assert_array_equal(get_color(image, (0, 0, 4, 4)), get_color(image))

    def test_does_not_mutate_the_source(self, rgb):
        before = rgb.copy()
        get_color(rgb, (0, 0, 1, 1))
        np.testing.assert_array_equal(rgb, before)


# ==============================================================================
# color_similarity / color_similar / color_similar_1d
# ==============================================================================


class TestColorSimilarity:
    def test_identical_colors_have_zero_similarity(self):
        assert color_similarity((10, 20, 30), (10, 20, 30)) == 0

    def test_tolerance_spans_both_directions(self):
        # diffs (-190, 180, -160): max positive 180, max negative -190
        assert color_similarity((10, 200, 30), (200, 20, 190)) == 370

    def test_tolerance_is_the_full_span_not_the_largest_gap(self):
        # diffs (-5, 5, -3): span is 10 even though no single channel moved 10
        assert color_similarity((100, 100, 100), (105, 95, 103)) == 10

    def test_all_positive_diffs_use_the_maximum(self):
        assert color_similarity((0, 0, 0), (1, 9, 4)) == 9

    def test_all_negative_diffs_use_the_most_negative(self):
        assert color_similarity((1, 9, 4), (0, 0, 0)) == 9

    def test_is_symmetric(self):
        a, b = (10, 200, 30), (200, 20, 190)
        assert color_similarity(a, b) == color_similarity(b, a)

    def test_accepts_floats(self):
        assert color_similarity((0.0, 0.0, 0.0), (0.5, 0.5, 0.5)) == 0.5

    def test_accepts_sequences_without_numpy(self):
        # Alasio dropped the numpy round trip, a plain list must work
        assert color_similarity([10, 20, 30], (10, 20, 30)) == 0

    def test_color_similar_applies_the_threshold_inclusively(self):
        a, b = (10, 200, 30), (200, 20, 190)
        assert color_similarity(a, b) == 370
        assert color_similar(a, b, threshold=370)
        assert not color_similar(a, b, threshold=369)

    def test_color_similar_defaults_to_threshold_10(self):
        assert color_similar((0, 0, 0), (10, 0, 0))
        assert not color_similar((0, 0, 0), (11, 0, 0))

    def test_color_similar_1d_matches_the_scalar_rule_per_row(self):
        image = np.array([[10, 0, 0], [11, 0, 0]], dtype=np.uint8)
        result = color_similar_1d(image, (0, 0, 0), 10)
        np.testing.assert_array_equal(result, [True, False])

    def test_color_similar_1d_returns_a_boolean_mask(self):
        image = np.array([[10, 200, 30]], dtype=np.uint8)
        assert color_similar_1d(image, (0, 0, 0), 5).dtype == np.bool_


# ==============================================================================
# color_similarity_2d / color_mask
# ==============================================================================

# The 3-channel path runs below 30000 pixels, the per-channel path above it.
SMALL = (100, 100)
LARGE = (200, 200)


class TestColorSimilarity2D:
    def test_exact_match_scores_255(self):
        image = np.full((4, 4, 3), (10, 20, 30), dtype=np.uint8)
        np.testing.assert_array_equal(color_similarity_2d(image, (10, 20, 30)), np.full((4, 4), 255, np.uint8))

    def test_score_is_255_minus_the_saturated_distance(self):
        # colour 10 units away on every channel -> distance 10 -> 245
        image = np.full((4, 4, 3), (10, 20, 30), dtype=np.uint8)
        np.testing.assert_array_equal(color_similarity_2d(image, (20, 30, 40)), np.full((4, 4), 245, np.uint8))

    def test_both_paths_agree_across_the_pixel_threshold(self):
        assert SMALL[0] * SMALL[1] < 30000 <= LARGE[0] * LARGE[1]
        for shape in (SMALL, LARGE):
            image = np.full((*shape, 3), (10, 20, 30), dtype=np.uint8)
            np.testing.assert_array_equal(
                color_similarity_2d(image, (10, 20, 30)),
                np.full(shape, 255, np.uint8),
            )

    def test_mixed_pixels_land_between_the_extremes(self):
        image = np.zeros((1, 3, 3), dtype=np.uint8)
        image[0, 0] = (10, 20, 30)
        image[0, 2] = (10, 20, 40)
        bar = color_similarity_2d(image, (10, 20, 30))
        assert bar[0, 0] == 255
        assert bar[0, 2] == 245

    def test_does_not_mutate_the_source(self):
        image = np.full((4, 4, 3), (10, 20, 30), dtype=np.uint8)
        before = image.copy()
        color_similarity_2d(image, (200, 200, 200))
        np.testing.assert_array_equal(image, before)


class TestColorMask:
    def test_output_is_binary(self):
        image = np.full((8, 8, 3), (10, 20, 30), dtype=np.uint8)
        assert set(np.unique(color_mask(image, (10, 20, 30)))).issubset({0, 255})

    def test_threshold_boundary_is_inclusive(self):
        # saturated distance is 10, so threshold 10 matches and 9 does not
        image = np.full((1, 1, 3), (10, 0, 0), dtype=np.uint8)
        assert color_mask(image, (0, 0, 0), threshold=10)[0, 0] == 255
        assert color_mask(image, (0, 0, 0), threshold=9)[0, 0] == 0

    def test_both_paths_agree_across_the_pixel_threshold(self):
        assert SMALL[0] * SMALL[1] < 30000 <= LARGE[0] * LARGE[1]
        for shape in (SMALL, LARGE):
            image = np.full((*shape, 3), (10, 20, 30), dtype=np.uint8)
            np.testing.assert_array_equal(color_mask(image, (10, 20, 30)), np.full(shape, 255, np.uint8))

    def test_agrees_with_color_similar_on_the_same_pixel(self):
        image = np.array([[[0, 0, 0], [7, 7, 7], [40, 0, 0]]], dtype=np.uint8)
        mask = color_mask(image, (0, 0, 0), threshold=30)
        expected = [[color_similar(pixel, (0, 0, 0), threshold=30) for pixel in row] for row in image]
        np.testing.assert_array_equal(mask > 0, np.array(expected))


# ==============================================================================
# extract_letters / extract_white_letters
# ==============================================================================


class TestExtractLetters:
    def test_white_letter_on_black_uses_the_fast_path(self):
        image = np.zeros((2, 2, 3), dtype=np.uint8)
        image[0, 0] = (255, 255, 255)
        result = extract_letters(image, threshold=255)
        assert result[0, 0] == 0  # letter turns black
        assert result[1, 1] == 255  # background turns white

    def test_coloured_letter_on_grey_background(self):
        image = np.full((2, 2, 3), 128, dtype=np.uint8)
        image[0, 0] = (255, 0, 0)
        result = extract_letters(image, letter=(255, 0, 0), threshold=255)
        assert result[0, 0] == 0
        assert result[1, 1] == 255

    def test_threshold_255_skips_the_scaling_step(self):
        # MAX(255 - 200) = 55 survives untouched when threshold is 255
        image = np.full((2, 2, 3), 200, dtype=np.uint8)
        np.testing.assert_array_equal(extract_letters(image, threshold=255), np.full((2, 2), 55, np.uint8))

    def test_lower_threshold_widens_what_counts_as_letter(self):
        image = np.full((1, 1, 3), 200, dtype=np.uint8)
        assert extract_letters(image, threshold=64)[0, 0] > extract_letters(image, threshold=255)[0, 0]

    def test_both_paths_agree_across_the_pixel_threshold(self):
        assert SMALL[0] * SMALL[1] < 30000 <= LARGE[0] * LARGE[1]
        for shape in (SMALL, LARGE):
            image = np.full((*shape, 3), 90, dtype=np.uint8)
            image[0, 0] = (30, 60, 90)
            result = extract_letters(image, letter=(30, 60, 90))
            assert result[0, 0] == 0
            assert set(np.unique(result)) == {0, 120}


class TestExtractWhiteLetters:
    # Letters are black in the output, backgrounds white. Coloured pixels are
    # pushed towards the background so they are not mistaken for letters.
    @pytest.mark.parametrize(
        "color, threshold, expected",
        [
            ((0, 0, 0), 128, 255),  # black background -> white
            ((0, 0, 0), 255, 128),  # same pixel, scale skipped
            ((255, 255, 255), 128, 0),  # white letter -> black
            ((128, 128, 128), 128, 128),  # mid grey -> half
            ((128, 128, 128), 255, 64),
            ((255, 0, 0), 128, 255),  # coloured -> background
        ],
    )
    def test_known_pixels(self, color, threshold, expected):
        assert extract_white_letters(np.array([[color]], np.uint8), threshold=threshold)[0, 0] == expected

    def test_output_is_two_dimensional(self):
        assert extract_white_letters(np.zeros((3, 4, 3), np.uint8)).shape == (3, 4)