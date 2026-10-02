"""
Tests for script.misc.image.imfile

Verbatim copy of alasio/base/image/imfile.py, so Alasio has no reference tests
for it. Covers the array helpers (image_channel/size/shape/copy/crop), the BGR
<-> RGB conversion pair, the encode/decode pair and the file level load/save.
"""
import cv2
import numpy as np
import pytest

from script.misc.image.imfile import (
    ImageBroken,
    ImageNotSupported,
    crop,
    cvt_color_decode,
    cvt_color_encode,
    gif_load,
    image_channel,
    image_copy,
    image_decode,
    image_encode,
    image_fixup,
    image_fixup_any,
    image_load,
    image_save,
    image_shape,
    image_size,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def grey():
    return np.full((4, 6), 90, dtype=np.uint8)


@pytest.fixture
def rgb():
    return np.zeros((4, 6, 3), dtype=np.uint8)


@pytest.fixture
def rgba():
    return np.zeros((4, 6, 4), dtype=np.uint8)


@pytest.fixture
def png(tmp_path):
    """A real 4x6 RGB png on disk plus the array it holds."""
    image = np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3)
    file = str(tmp_path / "sample.png")
    assert image_save(file, image) is True
    return file, image


# ==============================================================================
# image_channel / image_size / image_shape / image_copy
# ==============================================================================


class TestImageIntrospection:
    @pytest.mark.parametrize(
        "shape, channel",
        [((4, 6), 1), ((4, 6, 1), 1), ((4, 6, 3), 3), ((4, 6, 4), 4)],
    )
    def test_image_channel(self, shape, channel):
        assert image_channel(np.zeros(shape, np.uint8)) == channel

    def test_image_channel_is_width_height_independent(self):
        assert image_channel(np.zeros((1, 100, 3), np.uint8)) == 3

    def test_image_size_is_width_then_height(self, grey, rgb):
        assert image_size(grey) == (6, 4)
        assert image_size(rgb) == (6, 4)

    def test_image_shape_adds_the_channel(self, grey, rgb, rgba):
        assert image_shape(grey) == (6, 4, 1)
        assert image_shape(rgb) == (6, 4, 3)
        assert image_shape(rgba) == (6, 4, 4)

    def test_image_size_agrees_with_image_shape(self, rgb):
        w, h = image_size(rgb)
        assert (w, h, image_channel(rgb)) == image_shape(rgb)


class TestImageCopy:
    def test_equal_but_distinct_buffer(self, rgb):
        copied = image_copy(rgb)
        np.testing.assert_array_equal(copied, rgb)
        assert copied is not rgb
        assert copied.ctypes.data != rgb.ctypes.data

    def test_writing_the_copy_does_not_touch_the_source(self, rgb):
        copied = image_copy(rgb)
        copied[0, 0] = 255
        assert rgb[0, 0, 0] == 0


# ==============================================================================
# crop
# ==============================================================================


class TestCrop:
    def test_interior_crop(self, rgb):
        assert crop(rgb, (1, 1, 3, 3)).shape == (2, 2, 3)

    def test_full_area_copies_by_default(self, rgb):
        out = crop(rgb, (0, 0, 6, 4))
        np.testing.assert_array_equal(out, rgb)
        assert out.ctypes.data != rgb.ctypes.data

    def test_copy_false_returns_a_view(self, rgb):
        out = crop(rgb, (0, 0, 6, 4), copy=False)
        assert out.ctypes.data == rgb.ctypes.data

    def test_copy_true_returns_a_copy(self, rgb):
        out = crop(rgb, (0, 0, 6, 4), copy=True)
        assert out.ctypes.data != rgb.ctypes.data

    def test_out_of_bounds_is_padded_with_black(self):
        image = np.full((4, 4, 3), 255, dtype=np.uint8)
        out = crop(image, (-1, -1, 2, 2))
        assert out.shape == (3, 3, 3)
        # the 1px top/left border is black, the rest is the original
        assert not out[0, :].any()
        assert not out[:, 0].any()
        assert out[1:, 1:].all()

    def test_out_of_bounds_keeps_the_requested_size(self):
        image = np.full((4, 4), 255, dtype=np.uint8)
        out = crop(image, (2, 2, 8, 8))
        assert out.shape == (6, 6)
        assert out[:2, :2].all()
        assert not out[2:, 2:].any()

    def test_fully_outside_returns_black_at_the_requested_size(self):
        image = np.full((4, 4, 3), 255, dtype=np.uint8)
        # y1 <= 0 and x2 <= 0 -> overflow branch, no copyMakeBorder
        out = crop(image, (-5, -5, -3, -3))
        assert out.shape == (2, 2, 3)
        assert not out.any()

    def test_fully_outside_on_the_right(self):
        image = np.full((4, 4), 255, dtype=np.uint8)
        out = crop(image, (10, 10, 12, 12))
        assert out.shape == (2, 2)
        assert not out.any()

    def test_coordinates_are_rounded(self, rgb):
        assert crop(rgb, (1.4, 1.4, 2.6, 2.6)).shape == crop(rgb, (1, 1, 3, 3)).shape

    def test_preserves_dtype(self):
        image = np.full((4, 4), 7, dtype=np.uint16)
        assert crop(image, (-1, -1, 2, 2)).dtype == np.uint16

    def test_does_not_mutate_the_source(self, rgb):
        before = rgb.copy()
        crop(rgb, (-1, -1, 2, 2))
        np.testing.assert_array_equal(rgb, before)


# ==============================================================================
# cvt_color_decode / cvt_color_encode
# ==============================================================================


class TestCvtColorDecode:
    def test_three_channels_swap_bgr_to_rgb_in_place(self):
        image = np.array([[[10, 20, 30]]], dtype=np.uint8)
        out = cvt_color_decode(image)
        assert out is image
        np.testing.assert_array_equal(out, np.array([[[30, 20, 10]]], np.uint8))

    def test_grayscale_passes_through_untouched(self, grey):
        before = grey.copy()
        assert cvt_color_decode(grey) is grey
        np.testing.assert_array_equal(grey, before)

    def test_rgba_drops_alpha_and_swaps(self):
        image = np.array([[[10, 20, 30, 40]]], dtype=np.uint8)
        np.testing.assert_array_equal(cvt_color_decode(image), np.array([[[30, 20, 10]]], np.uint8))

    def test_area_crops_and_returns_a_new_array(self, rgb):
        rgb[0, 0] = (1, 2, 3)
        out = cvt_color_decode(rgb, area=(0, 0, 2, 2))
        assert out is not rgb
        assert out.shape == (2, 2, 3)
        np.testing.assert_array_equal(out[0, 0], (3, 2, 1))

    def test_two_channels_are_rejected(self):
        with pytest.raises(ImageNotSupported):
            cvt_color_decode(np.zeros((4, 6, 2), np.uint8))


class TestCvtColorEncode:
    def test_three_channels_swap_rgb_to_bgr(self):
        image = np.array([[[10, 20, 30]]], dtype=np.uint8)
        np.testing.assert_array_equal(cvt_color_encode(image), np.array([[[30, 20, 10]]], np.uint8))

    def test_grayscale_is_returned_unchanged(self, grey):
        assert cvt_color_encode(grey) is grey

    def test_rgba_keeps_alpha_and_swaps(self):
        image = np.array([[[10, 20, 30, 40]]], dtype=np.uint8)
        np.testing.assert_array_equal(cvt_color_encode(image), np.array([[[30, 20, 10, 40]]], np.uint8))

    def test_two_channels_are_rejected(self):
        with pytest.raises(ImageNotSupported):
            cvt_color_encode(np.zeros((4, 6, 2), np.uint8))

    def test_round_trips_through_decode(self, rgb):
        np.testing.assert_array_equal(cvt_color_decode(cvt_color_encode(rgb).copy()), rgb)


# ==============================================================================
# image_encode / image_decode
# ==============================================================================


class TestImageEncodeDecode:
    @pytest.mark.parametrize("ext", ["png", "PNG", "jpg", "jpeg", "webp", "tiff", "tif"])
    def test_known_extensions_encode(self, rgb, ext):
        data = image_encode(rgb, ext=ext)
        assert isinstance(data, np.ndarray)
        assert data.dtype == np.uint8
        assert data.size > 0

    def test_unknown_extension_is_rejected(self, rgb):
        with pytest.raises(ImageNotSupported):
            image_encode(rgb, ext="bmp")

    def test_explicit_encode_params_override_the_default(self, rgb):
        low = image_encode(rgb, ext="jpg", encode=[1, 1]).tobytes()
        high = image_encode(rgb, ext="jpg", encode=[1, 100]).tobytes()
        assert len(low) < len(high)

    def test_png_round_trip_is_lossless(self, rgb):
        data = image_encode(rgb, ext="png").tobytes()
        np.testing.assert_array_equal(image_decode(np.frombuffer(data, np.uint8)), rgb)

    def test_grayscale_round_trip(self, grey):
        data = image_encode(grey, ext="png").tobytes()
        out = image_decode(np.frombuffer(data, np.uint8))
        assert out.shape == grey.shape
        np.testing.assert_array_equal(out, grey)

    def test_decode_accepts_an_area(self, rgb):
        data = image_encode(rgb, ext="png").tobytes()
        out = image_decode(np.frombuffer(data, np.uint8), area=(1, 1, 3, 3))
        assert out.shape == (2, 2, 3)

    def test_garbage_bytes_raise(self):
        with pytest.raises(ImageBroken):
            image_decode(np.frombuffer(b"not an image at all", np.uint8))

    def test_empty_bytes_raise(self):
        # cv2.imdecode asserts on an empty buffer, so image_decode's own
        # `image is None` -> ImageBroken path is not reached here
        with pytest.raises(cv2.error):
            image_decode(np.frombuffer(b"", np.uint8))


# ==============================================================================
# image_load / image_save
# ==============================================================================


class TestImageLoadSave:
    def test_save_then_load_round_trips(self, tmp_path, rgb):
        file = str(tmp_path / "out.png")
        assert image_save(file, rgb) is True
        np.testing.assert_array_equal(image_load(file), rgb)

    def test_save_creates_missing_parent_directories(self, tmp_path, rgb):
        file = str(tmp_path / "a" / "b" / "out.png")
        assert image_save(file, rgb) is True
        assert image_load(file).shape == rgb.shape

    def test_load_with_an_area(self, tmp_path, rgb):
        file = str(tmp_path / "out.png")
        image_save(file, rgb)
        assert image_load(file, area=(1, 1, 3, 3)).shape == (2, 2, 3)

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            image_load(str(tmp_path / "nope.png"))

    def test_load_empty_file_raises(self, tmp_path):
        file = tmp_path / "empty.png"
        file.write_bytes(b"")
        with pytest.raises(ImageBroken):
            image_load(str(file))

    def test_skip_same_suppresses_an_identical_rewrite(self, tmp_path, rgb):
        file = str(tmp_path / "out.png")
        assert image_save(file, rgb, skip_same=True) is True
        before = (tmp_path / "out.png").read_bytes()
        assert image_save(file, rgb, skip_same=True) is False
        assert (tmp_path / "out.png").read_bytes() == before

    def test_skip_same_writes_when_content_changes(self, tmp_path, rgb):
        file = str(tmp_path / "out.png")
        image_save(file, rgb, skip_same=True)
        changed = rgb.copy()
        changed[0, 0] = 255
        assert image_save(file, changed, skip_same=True) is True

    def test_save_uses_the_extension_from_the_path(self, tmp_path, rgb):
        file = str(tmp_path / "out.webp")
        image_save(file, rgb)
        assert image_load(file).shape == rgb.shape

    def test_save_rejects_an_unknown_extension(self, tmp_path, rgb):
        with pytest.raises(ImageNotSupported):
            image_save(str(tmp_path / "out.bmp"), rgb)

    def test_save_leaves_no_temporary_files_behind(self, tmp_path, rgb):
        image_save(str(tmp_path / "out.png"), rgb)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["out.png"]


# ==============================================================================
# image_fixup / image_fixup_any
# ==============================================================================


class TestImageFixup:
    def test_missing_file_needs_no_fixup(self, tmp_path):
        assert image_fixup(str(tmp_path / "nope.png")) is False

    def test_empty_file_needs_no_fixup(self, tmp_path):
        file = tmp_path / "empty.png"
        file.write_bytes(b"")
        assert image_fixup(str(file)) is False

    def test_garbage_needs_no_fixup(self, tmp_path):
        file = tmp_path / "broken.png"
        file.write_bytes(b"definitely not a png")
        assert image_fixup(str(file)) is False

    def test_already_canonical_png_needs_no_fixup(self, tmp_path, rgb):
        file = str(tmp_path / "out.png")
        image_save(file, rgb)
        assert image_fixup(file) is False

    def test_rewrites_a_non_canonical_png(self, tmp_path, rgb):
        file = tmp_path / "loose.png"
        # level 0 compression is not what image_encode produces
        cv2.imwrite(str(file), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 0])
        assert image_fixup(str(file)) is True
        # and the rewritten file is now canonical
        assert image_fixup(str(file)) is False

    def test_need_crop_skips_a_full_screenshot_before_re_encoding(self, tmp_path):
        # non-canonical on purpose: the bbox gate must return False before the
        # re-encode would have noticed the difference
        image = np.full((8, 8, 3), 255, np.uint8)
        file = tmp_path / "full-loose.png"
        cv2.imwrite(str(file), cv2.cvtColor(image, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 0])
        assert image_fixup(str(file), need_crop=True) is False

    def test_need_crop_skips_a_pure_black_image(self, tmp_path):
        file = str(tmp_path / "black.png")
        image_save(file, np.zeros((8, 8, 3), np.uint8))
        assert image_fixup(file, need_crop=True) is False

    def test_need_crop_still_rewrites_content_smaller_than_the_frame(self, tmp_path):
        image = np.zeros((8, 8, 3), np.uint8)
        image[2:6, 2:6] = 255
        file = tmp_path / "crop.png"
        cv2.imwrite(str(file), cv2.cvtColor(image, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 0])
        assert image_fixup(str(file), need_crop=True) is True


class TestImageFixupAny:
    def test_counts_fixed_files_in_a_directory(self, tmp_path):
        directory = tmp_path / "assets"
        (directory / "sub").mkdir(parents=True)
        image = np.zeros((8, 8, 3), np.uint8)
        image[2:6, 2:6] = 255
        loose = [directory / "a.png", directory / "sub" / "b.png"]
        for file in loose:
            cv2.imwrite(str(file), cv2.cvtColor(image, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 0])
        # a non-png is ignored
        (directory / "notes.txt").write_text("hello", encoding="utf-8")

        assert image_fixup_any(str(directory)) == 2
        assert image_fixup_any(str(directory)) == 0

    def test_accepts_a_single_png_path(self, tmp_path, rgb):
        file = str(tmp_path / "out.png")
        image_save(file, rgb)
        assert image_fixup_any(file) == 0

    def test_ignores_non_image_files(self, tmp_path):
        file = tmp_path / "notes.txt"
        file.write_text("hello", encoding="utf-8")
        assert image_fixup_any(str(file)) == 0


# ==============================================================================
# gif_load
# ==============================================================================


class TestGifLoad:
    def test_missing_gif_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            gif_load(str(tmp_path / "nope.gif"))

    def test_fframe_of_a_missing_gif_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            from script.misc.image.imfile import gif_load_fframe

            gif_load_fframe(str(tmp_path / "nope.gif"))

    def test_image_load_dispatches_gif_to_the_video_capture_path(self, tmp_path):
        # image_load routes .gif to gif_load_fframe, which needs a real gif
        with pytest.raises((FileNotFoundError, ImageBroken)):
            image_load(str(tmp_path / "nope.gif"))