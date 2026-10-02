import time

import cv2

from script.misc.image.imfile import image_encode


def image_preview(image, now=None, quality=75):
    """
    Create a preview

    Args:
        image (np.ndarray): Input image
        now (float | None): Time in second, or 0 or None for now
        quality (int): JPEG quality, 0~100, bigger for better quality

    Returns:
        bytes: Formatted preview data
            b'Preview_' + big-endian millisecond timestamp + JPG image in bytes
            Note that preview message always have 8 bytes of header, 8 bytes of timestamp, and optional data
    """
    # Use 0.5 scale factor to leverage OpenCV internal optimizations
    res = cv2.resize(image, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    data = image_encode(res, ext='jpg', encode=[cv2.IMWRITE_JPEG_QUALITY, quality]).tobytes()
    if now is None or now <= 0:
        now = int(time.time() * 1000)
    else:
        now = int(now * 1000)
    return b''.join((b'Preview_', now.to_bytes(8, 'big'), data))


def image_preview_stop(now=None):
    """
    Create a stop signal

    Args:
        now (float | None): Time in second, or 0 or None for now

    Returns:
        bytes: Formatted stop signal
            b'PreviewS' + big-endian millisecond timestamp
    """
    if now is None or now <= 0:
        now = int(time.time() * 1000)
    else:
        now = int(now * 1000)
    return b''.join((b'PreviewS', now.to_bytes(8, 'big')))
