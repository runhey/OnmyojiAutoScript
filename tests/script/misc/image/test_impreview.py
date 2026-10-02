"""
Tests for script.misc.image.impreview

Verbatim copy of alasio/base/image/impreview.py, so Alasio has no reference
tests for it. The wire format is asserted against the layout documented in the
docstrings: an 8 byte magic followed by a big-endian millisecond timestamp.
"""
import time

import cv2
import numpy as np

from script.misc.image.impreview import image_preview, image_preview_stop

# ==============================================================================
# Fixtures
# ==============================================================================


def _make_image(height=40, width=60):
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[10:30, 20:50] = (200, 100, 50)
    return image


# ==============================================================================
# image_preview
# ==============================================================================


class TestImagePreview:
    def test_starts_with_the_documented_magic(self):
        assert image_preview(_make_image(), now=1.5).startswith(b"Preview_")

    def test_header_is_eight_bytes(self):
        assert len(image_preview(_make_image(), now=1.5)) > 8
        assert image_preview_stop(now=1.5).startswith(b"PreviewS")

    def test_timestamp_is_big_endian_milliseconds(self):
        data = image_preview(_make_image(), now=1.5)
        assert int.from_bytes(data[8:16], "big") == 1500

    def test_stop_signal_is_magic_plus_timestamp(self):
        assert image_preview_stop(now=1.5) == b"PreviewS" + (1500).to_bytes(8, "big")
        assert len(image_preview_stop(now=1.5)) == 16

    def test_sub_second_input_is_scaled_to_milliseconds(self):
        data = image_preview(_make_image(), now=0.001)
        assert int.from_bytes(data[8:16], "big") == 1

    def test_none_and_zero_use_the_wall_clock(self):
        before = int(time.time() * 1000)
        for now in (None, 0, -1):
            stamp = int.from_bytes(image_preview_stop(now)[8:16], "big")
            assert before - 1000 <= stamp <= int(time.time() * 1000) + 1000

    def test_payload_is_a_decodable_jpeg(self):
        data = image_preview(_make_image(), now=1.5)
        decoded = cv2.imdecode(np.frombuffer(data[16:], np.uint8), cv2.IMREAD_UNCHANGED)
        assert decoded is not None
        assert decoded.ndim == 3

    def test_image_is_halved_before_encoding(self):
        # the implementation resizes with fx=fy=0.5
        data = image_preview(_make_image(height=40, width=60), now=1.5)
        decoded = cv2.imdecode(np.frombuffer(data[16:], np.uint8), cv2.IMREAD_UNCHANGED)
        assert decoded.shape[:2] == (20, 30)

    def test_lower_quality_produces_fewer_bytes(self):
        image = _make_image()
        assert len(image_preview(image, now=1.5, quality=10)) < len(image_preview(image, now=1.5, quality=95))

    def test_grayscale_input_is_accepted(self):
        data = image_preview(np.full((40, 60), 128, np.uint8), now=1.5)
        assert data.startswith(b"Preview_")


# ==============================================================================
# image_preview_stop
# ==============================================================================


class TestImagePreviewStop:
    def test_payload_is_exactly_sixteen_bytes(self):
        assert len(image_preview_stop(now=12345.678)) == 16

    def test_does_not_carry_image_data(self):
        assert image_preview_stop(now=1.5)[8:] == (1500).to_bytes(8, "big")

    def test_same_input_gives_the_same_bytes(self):
        assert image_preview_stop(now=7.5) == image_preview_stop(now=7.5)