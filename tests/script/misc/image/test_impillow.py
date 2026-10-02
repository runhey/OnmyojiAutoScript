"""
Tests for script.misc.image.impillow

Verbatim copy of alasio/base/image/impillow.py, so Alasio has no reference
tests for it. These are the slow pillow paths; image_load/image_save in
imfile.py are the ones used in production.
"""
import numpy as np
import pytest

from script.misc.image.imfile import ImageNotSupported
from script.misc.image.impillow import image_load_pillow, image_save_pillow

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def rgb():
    image = np.zeros((4, 6, 3), dtype=np.uint8)
    image[1, 2] = (10, 20, 30)
    image[3, 5] = (200, 100, 50)
    return image


# ==============================================================================
# image_save_pillow / image_load_pillow
# ==============================================================================


class TestPillowRoundTrip:
    def test_rgb_round_trips(self, tmp_path, rgb):
        file = str(tmp_path / "out.png")
        assert image_save_pillow(file, rgb) is True
        np.testing.assert_array_equal(image_load_pillow(file), rgb)

    def test_grayscale_round_trips(self, tmp_path):
        image = np.arange(4 * 6, dtype=np.uint8).reshape(4, 6)
        file = str(tmp_path / "out.png")
        image_save_pillow(file, image)
        np.testing.assert_array_equal(image_load_pillow(file), image)

    def test_load_drops_the_alpha_channel(self, tmp_path):
        image = np.zeros((4, 6, 4), dtype=np.uint8)
        image[0, 0] = (10, 20, 30, 40)
        file = str(tmp_path / "out.png")
        image_save_pillow(file, image)
        loaded = image_load_pillow(file)
        assert loaded.shape == (4, 6, 3)
        assert tuple(loaded[0, 0]) == (10, 20, 30)

    def test_load_with_an_area(self, tmp_path, rgb):
        file = str(tmp_path / "out.png")
        image_save_pillow(file, rgb)
        assert image_load_pillow(file, area=(1, 1, 3, 3)).shape == (2, 2, 3)

    def test_save_creates_missing_parent_directories(self, tmp_path, rgb):
        file = str(tmp_path / "a" / "b" / "out.png")
        assert image_save_pillow(file, rgb) is True
        assert image_load_pillow(file).shape == rgb.shape

    def test_save_uses_the_extension_from_the_path(self, tmp_path, rgb):
        file = str(tmp_path / "out.bmp")
        image_save_pillow(file, rgb)
        assert image_load_pillow(file).shape == rgb.shape

    def test_leaves_no_temporary_files_behind(self, tmp_path, rgb):
        image_save_pillow(str(tmp_path / "out.png"), rgb)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["out.png"]

    def test_overwrites_an_existing_file(self, tmp_path, rgb):
        file = str(tmp_path / "out.png")
        image_save_pillow(file, rgb)
        other = np.zeros((4, 6, 3), np.uint8)
        image_save_pillow(file, other)
        np.testing.assert_array_equal(image_load_pillow(file), other)


class TestPillowErrors:
    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            image_load_pillow(str(tmp_path / "nope.png"))

    def test_load_broken_file_raises(self, tmp_path):
        # PIL raises UnidentifiedImageError, a subclass of OSError. The module
        # docstring advertises ImageBroken but the code does not wrap PIL errors.
        file = tmp_path / "broken.png"
        file.write_bytes(b"not a png")
        with pytest.raises(OSError):
            image_load_pillow(str(file))

    def test_save_rejects_an_unsupported_channel_count(self, tmp_path):
        with pytest.raises(ImageNotSupported):
            image_save_pillow(str(tmp_path / "out.png"), np.zeros((4, 6, 2), np.uint8))