"""
Tests for script.misc.image.imgif

Verbatim copy of alasio/base/image/imgif.py, so Alasio has no reference tests
for it. Whole module is skipped when imageio is not installed.
"""
import numpy as np
import pytest

pytest.importorskip("imageio", reason="script.misc.image.imgif requires imageio")

from script.misc.image.imgif import gif_load_imageio, gif_save_imageio, mimsave  # noqa: E402

# ==============================================================================
# Fixtures
# ==============================================================================


def _frame(value):
    image = np.zeros((8, 12, 3), dtype=np.uint8)
    image[2:6, 3:9] = value
    return image


@pytest.fixture
def gif(tmp_path):
    """A two frame gif on disk."""
    file = str(tmp_path / "sample.gif")
    gif_save_imageio([_frame((255, 0, 0)), _frame((0, 255, 0))], file, fps=5)
    return file


# ==============================================================================
# gif_save_imageio / gif_load_imageio
# ==============================================================================


class TestGifRoundTrip:
    def test_reads_every_frame(self, gif):
        frames = gif_load_imageio(gif)
        assert len(frames) == 2

    def test_frame_order_is_preserved(self, gif):
        frames = gif_load_imageio(gif)
        assert tuple(frames[0][3, 5]) == (255, 0, 0)
        assert tuple(frames[1][3, 5]) == (0, 255, 0)

    def test_untouched_pixels_stay_black(self, gif):
        frames = gif_load_imageio(gif)
        assert tuple(frames[0][0, 0]) == (0, 0, 0)

    def test_load_with_an_area(self, gif):
        frames = gif_load_imageio(gif, area=(3, 2, 9, 6))
        assert frames[0].shape == (4, 6, 3)

    def test_load_drops_the_alpha_channel(self, tmp_path):
        file = str(tmp_path / "alpha.gif")
        frame = np.zeros((8, 12, 4), dtype=np.uint8)
        frame[2:6, 3:9] = (10, 20, 30, 40)
        gif_save_imageio([frame], file, fps=5)
        loaded = gif_load_imageio(file)
        assert loaded[0].shape == (8, 12, 3)

    def test_save_creates_missing_parent_directories(self, tmp_path):
        file = str(tmp_path / "a" / "b" / "out.gif")
        gif_save_imageio([_frame((1, 2, 3))], file, fps=5)
        assert len(gif_load_imageio(file)) == 1

    def test_save_uses_the_extension_from_the_path(self, tmp_path):
        file = str(tmp_path / "out.gif")
        gif_save_imageio([_frame((1, 2, 3))], file, fps=5)
        assert len(gif_load_imageio(file)) == 1

    def test_leaves_no_temporary_files_behind(self, tmp_path):
        file = str(tmp_path / "out.gif")
        gif_save_imageio([_frame((1, 2, 3))], file, fps=5)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["out.gif"]


class TestMimsaveShim:
    def test_fps_is_translated_to_duration(self, tmp_path):
        # imageio >= 2.21.3 rejects fps=, so the module wraps it
        file = str(tmp_path / "out.gif")
        mimsave(file, [_frame((1, 2, 3))], format="gif", fps=4)
        assert len(gif_load_imageio(file)) == 1

    def test_no_fps_still_works(self, tmp_path):
        file = str(tmp_path / "out.gif")
        mimsave(file, [_frame((1, 2, 3))], format="gif")
        assert len(gif_load_imageio(file)) == 1