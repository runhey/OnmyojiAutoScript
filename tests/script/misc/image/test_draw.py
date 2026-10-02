"""
Tests for script.misc.image.draw

Verbatim copy of alasio/base/image/draw.py, so Alasio has no reference tests
for it. Covers resize, the paste/paint mutators and the two bbox variants.

show_as_pillow() is deliberately untested: it opens an OS image viewer.
"""
import numpy as np
import pytest

from script.misc.image.draw import (
    get_bbox,
    get_bbox_reversed,
    image_paint,
    image_paint_black,
    image_paint_white,
    image_paste,
    resize,
    resize_maxpx,
)
from script.misc.image.imfile import ImageNotSupported

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def rgb():
    return np.zeros((4, 6, 3), dtype=np.uint8)


# ==============================================================================
# resize / resize_maxpx
# ==============================================================================


class TestResize:
    def test_size_is_width_then_height(self, rgb):
        # the array is 4 tall by 6 wide
        assert resize(rgb, (10, 20)).shape == (20, 10, 3)

    def test_grayscale_keeps_two_dimensions(self):
        assert resize(np.zeros((4, 6), np.uint8), (3, 3)).shape == (3, 3)

    def test_nearest_interpolation_keeps_flat_blocks(self):
        image = np.zeros((2, 2), np.uint8)
        image[0, 0] = 255
        assert set(np.unique(resize(image, (4, 4)))).issubset({0, 255})

    def test_same_size_is_a_noop_in_shape(self, rgb):
        assert resize(rgb, (6, 4)).shape == rgb.shape


class TestResizeMaxPx:
    def test_returns_the_same_object_when_already_small(self, rgb):
        # 6x4 is smaller than maxpx 10 on both axes
        assert resize_maxpx(rgb, 10) is rgb

    def test_boundaries_equal_to_maxpx_are_left_alone(self):
        image = np.zeros((10, 10, 3), np.uint8)
        assert resize_maxpx(image, 10) is image

    def test_landscape_is_limited_by_width(self):
        image = np.zeros((10, 20, 3), np.uint8)  # w=20 h=10
        assert resize_maxpx(image, 10).shape == (5, 10, 3)

    def test_portrait_is_limited_by_height(self):
        image = np.zeros((20, 10, 3), np.uint8)  # w=10 h=20
        assert resize_maxpx(image, 10).shape == (10, 5, 3)

    def test_square_only_needs_one_axis(self):
        image = np.zeros((20, 20, 3), np.uint8)
        assert resize_maxpx(image, 10).shape == (10, 10, 3)

    def test_never_exceeds_maxpx_on_either_axis(self):
        image = np.zeros((37, 91, 3), np.uint8)
        out = resize_maxpx(image, 40)
        assert out.shape[1] <= 40
        assert out.shape[0] <= 40


# ==============================================================================
# image_paste / image_paint / image_paint_white / image_paint_black
# ==============================================================================


class TestImagePaste:
    def test_pastes_at_the_origin_and_mutates_the_background(self, rgb):
        patch = np.full((2, 3, 3), 200, dtype=np.uint8)
        image_paste(patch, rgb, (1, 1))
        assert rgb[1, 3, 0] == 200
        assert rgb[0, 0, 0] == 0
        assert rgb[3, 0, 0] == 0

    def test_returns_none_and_updates_in_place(self, rgb):
        assert image_paste(np.full((1, 1, 3), 7, np.uint8), rgb, (0, 0)) is None
        assert rgb[0, 0, 0] == 7

    def test_copies_a_read_only_source(self, rgb):
        patch = np.full((2, 2, 3), 90, dtype=np.uint8)
        patch.flags.writeable = False
        image_paste(patch, rgb, (0, 0))
        assert rgb[0, 0, 0] == 90


class TestImagePaint:
    def test_paints_the_area(self, rgb):
        image_paint(rgb, (1, 1, 3, 3), (10, 20, 30))
        assert tuple(rgb[1, 1]) == (10, 20, 30)
        assert tuple(rgb[0, 0]) == (0, 0, 0)
        assert tuple(rgb[2, 2]) == (10, 20, 30)

    def test_outside_the_area_is_untouched(self, rgb):
        image_paint(rgb, (1, 1, 3, 3), (255, 255, 255))
        assert not rgb[0, :].any()
        assert not rgb[:, 0].any()

    def test_copies_a_read_only_source(self, rgb):
        rgb.flags.writeable = False
        image_paint(rgb, (0, 0, 2, 2), (5, 5, 5))
        assert not rgb.flags.writeable
        assert tuple(rgb[0, 0]) == (0, 0, 0)


class TestImagePaintWhiteBlack:
    @pytest.mark.parametrize(
        "channel, white, black",
        [
            (3, (255, 255, 255), (0, 0, 0)),
            (4, (255, 255, 255, 255), (0, 0, 0, 255)),
        ],
    )
    def test_colour_images(self, channel, white, black):
        image = np.zeros((4, 4, channel), np.uint8)
        image_paint_white(image, (1, 1, 3, 3))
        assert tuple(image[1, 1]) == white
        image_paint_black(image, (1, 1, 3, 3))
        assert tuple(image[1, 1]) == black

    def test_grayscale_uses_a_scalar(self):
        image = np.zeros((4, 4), np.uint8)
        image_paint_white(image, (1, 1, 3, 3))
        assert image[1, 1] == 255
        image_paint_black(image, (1, 1, 3, 3))
        assert image[1, 1] == 0

    def test_outside_the_area_is_untouched(self):
        image = np.zeros((4, 4, 3), np.uint8)
        image_paint_white(image, (1, 1, 3, 3))
        assert not image[0, :].any()
        assert not image[:, 0].any()


# ==============================================================================
# get_bbox / get_bbox_reversed
# ==============================================================================


@pytest.fixture
def framed():
    """10x10 black image with one white block at rows 3..7, cols 2..5."""
    image = np.zeros((10, 10), np.uint8)
    image[3:8, 2:6] = 255
    return image


class TestGetBbox:
    def test_finds_the_content_block(self, framed):
        # boundingRect is (x, y, w, h) -> (2, 3, 4, 5)
        assert get_bbox(framed) == (2, 3, 6, 8)

    def test_full_white_image_is_the_whole_frame(self):
        assert get_bbox(np.full((10, 12), 255, np.uint8)) == (0, 0, 12, 10)

    def test_accepts_rgb(self):
        image = np.zeros((10, 10, 3), np.uint8)
        image[3:8, 2:6] = (255, 255, 255)
        assert get_bbox(image) == (2, 3, 6, 8)

    def test_accepts_rgba(self):
        image = np.zeros((10, 10, 4), np.uint8)
        image[3:8, 2:6] = (255, 255, 255, 255)
        assert get_bbox(image) == (2, 3, 6, 8)

    def test_two_blocks_give_the_union(self):
        image = np.zeros((20, 20), np.uint8)
        image[2:5, 2:5] = 255
        image[12:18, 10:16] = 255
        assert get_bbox(image) == (2, 2, 16, 18)

    def test_pure_black_raises(self):
        with pytest.raises(ImageNotSupported):
            get_bbox(np.zeros((10, 10), np.uint8))

    def test_threshold_excludes_dim_content(self):
        image = np.full((10, 10), 5, np.uint8)
        # content must be strictly greater than threshold
        with pytest.raises(ImageNotSupported):
            get_bbox(image, threshold=5)
        assert get_bbox(image, threshold=4) == (0, 0, 10, 10)

    def test_rejects_an_unsupported_channel_count(self):
        with pytest.raises(ImageNotSupported):
            get_bbox(np.zeros((10, 10, 2), np.uint8))


class TestGetBboxReversed:
    """
    NOTE: the docstring claims "color < threshold is content", but the code
    thresholds with `cv2.THRESH_BINARY` (not `_INV`) and a hardcoded thresh of
    0. The mask is therefore `threshold` wherever the pixel is non-black, and
    0 on black pixels. With RETR_EXTERNAL, an interior black block is a hole
    and gets ignored, so the bbox is the frame. These tests pin the actual
    behaviour; they are not a statement that it matches the docstring.
    """

    def test_matches_get_bbox_when_content_is_the_bright_region(self):
        # black background, white block -> masks to the same thing get_bbox sees
        image = np.zeros((10, 10), np.uint8)
        image[3:8, 2:6] = 255
        assert get_bbox_reversed(image) == (2, 3, 6, 8)

    def test_an_interior_black_block_is_a_hole_and_is_ignored(self):
        image = np.full((10, 10), 255, np.uint8)
        image[3:8, 2:6] = 0
        # RETR_EXTERNAL keeps only the outer contour, i.e. the image frame
        assert get_bbox_reversed(image) == (0, 0, 10, 10)

    def test_full_white_image_is_the_whole_frame(self):
        assert get_bbox_reversed(np.full((10, 12), 255, np.uint8)) == (0, 0, 12, 10)

    def test_pure_black_raises(self):
        with pytest.raises(ImageNotSupported):
            get_bbox_reversed(np.zeros((10, 10), np.uint8))

    def test_non_zero_threshold_only_changes_the_mask_value(self):
        image = np.zeros((10, 10), np.uint8)
        image[3:8, 2:6] = 255
        assert get_bbox_reversed(image, threshold=1) == get_bbox_reversed(image, threshold=255) == (2, 3, 6, 8)

    def test_threshold_zero_blanks_the_mask(self):
        with pytest.raises(ImageNotSupported):
            get_bbox_reversed(np.full((10, 10), 255, np.uint8), threshold=0)

    def test_accepts_rgb(self):
        image = np.zeros((10, 10, 3), np.uint8)
        image[3:8, 2:6] = 255
        assert get_bbox_reversed(image) == (2, 3, 6, 8)

    def test_accepts_rgba(self):
        image = np.zeros((10, 10, 4), np.uint8)
        image[3:8, 2:6] = 255
        assert get_bbox_reversed(image) == (2, 3, 6, 8)

    def test_default_arguments_make_both_variants_agree(self):
        # both binarize at 0 with a non-zero maxval and use RETR_EXTERNAL, so
        # with default arguments the results are identical
        black_bg = np.zeros((10, 10), np.uint8)
        black_bg[3:8, 2:6] = 255
        white_bg = np.full((10, 10), 255, np.uint8)
        white_bg[3:8, 2:6] = 0
        assert get_bbox(black_bg) == get_bbox_reversed(black_bg) == (2, 3, 6, 8)
        assert get_bbox(white_bg) == get_bbox_reversed(white_bg) == (0, 0, 10, 10)

    def test_threshold_is_a_cutoff_for_get_bbox_but_a_mask_value_here(self):
        # dim pixel: get_bbox(threshold=10) rejects it, get_bbox_reversed
        # only uses threshold as the value written into the mask
        image = np.full((10, 10), 5, np.uint8)
        with pytest.raises(ImageNotSupported):
            get_bbox(image, threshold=10)
        assert get_bbox_reversed(image, threshold=10) == (0, 0, 10, 10)

    def test_rejects_an_unsupported_channel_count(self):
        with pytest.raises(ImageNotSupported):
            get_bbox_reversed(np.zeros((10, 10, 2), np.uint8))