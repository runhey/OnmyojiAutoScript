import cv2
import numpy as np

from script.misc.image.imfile import crop


def rgbmax(image):
    """
    rgbmax = MAX(r, g, b)
    with minimum memory copies

    Args:
        image (np.ndarray): Shape (height, width, channel)

    Returns:
        np.ndarray: Shape (height, width)
    """
    r, g, b = cv2.split(image)
    cv2.max(r, g, dst=r)
    cv2.max(r, b, dst=r)
    return r


def rgbmin(image):
    """
    rgbmax = MIN(r, g, b)
    with minimum memory copies

    Args:
        image (np.ndarray): Shape (height, width, channel)

    Returns:
        np.ndarray: Shape (height, width)
    """
    r, g, b = cv2.split(image)
    cv2.min(r, g, dst=r)
    cv2.min(r, b, dst=r)
    return r


def rgbminmax(image):
    """
    Get both min and max of RGB with minimum memory copies

    Args:
        image (np.ndarray): Shape (height, width, channel)

    Returns:
        np.ndarray: Shape (height, width)
        np.ndarray: Shape (height, width)
    """
    r, g, b = cv2.split(image)
    maximum = cv2.max(r, g)
    cv2.min(r, g, dst=r)
    cv2.max(maximum, b, dst=maximum)
    cv2.min(r, b, dst=r)
    # minimum = r
    return r, maximum


def rgb2gray(image):
    """
    gray = ( MAX(r, g, b) + MIN(r, g, b)) / 2

    Args:
        image (np.ndarray): Shape (height, width, channel)

    Returns:
        np.ndarray: Shape (height, width)
    """
    # r, g, b = cv2.split(image)
    # return cv2.add(
    #     cv2.multiply(cv2.max(cv2.max(r, g), b), 0.5),
    #     cv2.multiply(cv2.min(cv2.min(r, g), b), 0.5)
    # )
    r, g, b = cv2.split(image)
    maximum = cv2.max(r, g)
    cv2.min(r, g, dst=r)
    cv2.max(maximum, b, dst=maximum)
    cv2.min(r, b, dst=r)
    # minimum = r
    cv2.addWeighted(maximum, 0.5, r, 0.5, 0, dst=maximum)
    return maximum


def rgb2hsv(image):
    """
    Convert RGB color space to HSV color space.
    HSV is Hue Saturation Value.

    Args:
        image (np.ndarray): Shape (height, width, channel)

    Returns:
        np.ndarray: Hue (0~360), Saturation (0~100), Value (0~100).
    """
    image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype(float)
    cv2.multiply(image, (360 / 180, 100 / 255, 100 / 255, 0), dst=image)
    return image


def rgb2luma(image, fast=True):
    """
    Convert RGB to the Y channel (Luminance) in YUV color space.

    OpenCV calculates using:
        Y = (R * 4899 + G * 9617 + B * 1868 + 8192) >> 14

    Args:
        image (np.ndarray): Shape (height, width, channel)
        fast (bool): True to use faster implement that costs 12.624us on 1280x720 image instead of 15.084us
                Note that due to float calculation, this method has +- 1 color difference compares to standard opencv,
                which should be acceptable in template matching.
                If you do need a precise result, use `fast=False` instead

    Returns:
        np.ndarray: Shape (height, width)
    """
    if fast:
        r, g, b = cv2.split(image)
        luma = cv2.addWeighted(r, 0.299, g, 0.587, 0)
        cv2.addWeighted(luma, 1.0, b, 0.114, 0, dst=luma)
        return luma
    else:
        return cv2.extractChannel(cv2.cvtColor(image, cv2.COLOR_RGB2YUV), 0)


def rgb565_to_rgb888(image):
    """
    Args:
        image (np.ndarray): uint16 image in (height, width)
            Bit Layout: [ RRRRR (5) | GGGGGG (6) | BBBBB (5) ]

    Returns:
        np.ndarray: (height, width, 3)
    """
    # Convert RGB565 to RGB888
    # https://blog.csdn.net/happy08god/article/details/10516871

    # r = (arr & 0b1111100000000000) >> (11 - 3)
    # g = (arr & 0b0000011111100000) >> (5 - 2)
    # b = (arr & 0b0000000000011111) << 3
    # r |= (r & 0b11100000) >> 5
    # g |= (g & 0b11000000) >> 6
    # b |= (b & 0b11100000) >> 5
    # r = r.astype(np.uint8)
    # g = g.astype(np.uint8)
    # b = b.astype(np.uint8)
    # image = cv2.merge([r, g, b])

    # The same as the code above but costs about 2.7ms instead of 16ms.
    # Note that cv2.convertScaleAbs is 5x fast as cv2.multiply, cv2.add is 8x fast as cv2.convertScaleAbs
    # Note that cv2.convertScaleAbs includes rounding
    tmp = np.empty_like(image)
    cv2.bitwise_and(image, 0b1111100000000000, dst=tmp)
    r = cv2.convertScaleAbs(tmp, alpha=0.0040283203125)  # 0.00390625 * 1.03125
    cv2.bitwise_and(image, 0b0000011111100000, dst=tmp)
    g = cv2.convertScaleAbs(tmp, alpha=0.126953125)  # 0.125 * 1.015625
    cv2.bitwise_and(image, 0b0000000000011111, dst=tmp)
    b = cv2.convertScaleAbs(tmp, alpha=8.25)  # 8 * 1.03125

    image = cv2.merge([r, g, b])
    return image


def get_color(image, area=None):
    """Calculate the average color of a particular area of the image.

    Args:
        image (np.ndarray): Screenshot.
        area (tuple | None): (upper_left_x, upper_left_y, bottom_right_x, bottom_right_y)

    Returns:
        tuple: (r, g, b)
    """
    if area is not None:
        image = crop(image, area, copy=False)
    color = cv2.mean(image)
    return color[:3]


def color_similarity(color1, color2):
    """
    Args:
        color1 (tuple): (r, g, b)
        color2 (tuple): (r, g, b)

    Returns:
        int:
    """
    # print(color1, color2)
    # diff = np.array(color1).astype(int) - np.array(color2).astype(int)
    # diff = np.max(np.maximum(diff, 0)) - np.min(np.minimum(diff, 0))
    diff_r = color1[0] - color2[0]
    diff_g = color1[1] - color2[1]
    diff_b = color1[2] - color2[2]

    max_positive = 0
    max_negative = 0
    if diff_r > max_positive:
        max_positive = diff_r
    elif diff_r < max_negative:
        max_negative = diff_r
    if diff_g > max_positive:
        max_positive = diff_g
    elif diff_g < max_negative:
        max_negative = diff_g
    if diff_b > max_positive:
        max_positive = diff_b
    elif diff_b < max_negative:
        max_negative = diff_b

    diff = max_positive - max_negative
    return diff


def color_similar(color1, color2, threshold=10):
    """
    Consider two colors are similar, if tolerance lesser or equal threshold.
    Tolerance = Max(Positive(difference_rgb)) + Max(- Negative(difference_rgb))
    The same as the tolerance in Photoshop.

    Args:
        color1 (tuple): (r, g, b)
        color2 (tuple): (r, g, b)
        threshold (int): Default to 10.

    Returns:
        bool: True if two colors are similar.
    """
    # print(color1, color2)
    # diff = np.array(color1).astype(int) - np.array(color2).astype(int)
    # diff = np.max(np.maximum(diff, 0)) - np.min(np.minimum(diff, 0))
    diff_r = color1[0] - color2[0]
    diff_g = color1[1] - color2[1]
    diff_b = color1[2] - color2[2]

    max_positive = 0
    max_negative = 0
    if diff_r > max_positive:
        max_positive = diff_r
    elif diff_r < max_negative:
        max_negative = diff_r
    if diff_g > max_positive:
        max_positive = diff_g
    elif diff_g < max_negative:
        max_negative = diff_g
    if diff_b > max_positive:
        max_positive = diff_b
    elif diff_b < max_negative:
        max_negative = diff_b

    diff = max_positive - max_negative
    return diff <= threshold


def color_similar_1d(image, color, threshold=10):
    """
    Args:
        image (np.ndarray): 1D array.
        color: (r, g, b)
        threshold(int): Default to 10.

    Returns:
        np.ndarray: bool
    """
    diff = image.astype(int) - color
    diff = np.max(np.maximum(diff, 0), axis=1) - np.min(np.minimum(diff, 0), axis=1)
    return diff <= threshold


def color_similarity_2d(image, color):
    """
    Per-pixel color distance map: 255 when the pixel exactly matches color.

    result = 255 - sat_add(max_c(sat_sub(image - c)), max_c(sat_sub(c - image)))
    where c = (r, g, b), sat_sub/sat_add are uint8 saturating ops,
    max_c takes the per-pixel maximum across channels.

    Args:
        image: 2D array.
        color: (r, g, b)

    Returns:
        np.ndarray: uint8
    """
    # r, g, b = cv2.split(cv2.subtract(image, (*color, 0)))
    # positive = cv2.max(cv2.max(r, g), b)
    # r, g, b = cv2.split(cv2.subtract((*color, 0), image))
    # negative = cv2.max(cv2.max(r, g), b)
    # return cv2.subtract(255, cv2.add(positive, negative))
    h, w = image.shape[:2]
    if h * w < 30000:
        # The 3-channel path is faster on tiny images where per-call
        # overhead dominates
        diff = cv2.subtract(image, (*color, 0))
        r, g, b = cv2.split(diff)
        cv2.max(r, g, dst=r)
        cv2.max(r, b, dst=r)
        positive = r
        cv2.subtract((*color, 0), image, dst=diff)
        r, g, b = cv2.split(diff)
        cv2.max(r, g, dst=r)
        cv2.max(r, b, dst=r)
        negative = r
        cv2.add(positive, negative, dst=positive)
        cv2.bitwise_not(positive, dst=positive)
        return positive
    # Per-channel subtract with buffer reuse wins on larger images
    r, g, b = cv2.split(image)
    cr, cg, cb = color
    positive = cv2.subtract(r, cr)
    cv2.subtract(cr, r, dst=r)
    negative = r
    diff = cv2.subtract(g, cg)
    cv2.max(positive, diff, dst=positive)
    cv2.subtract(cg, g, dst=diff)
    cv2.max(negative, diff, dst=negative)
    cv2.subtract(b, cb, dst=diff)
    cv2.max(positive, diff, dst=positive)
    cv2.subtract(cb, b, dst=diff)
    cv2.max(negative, diff, dst=negative)
    cv2.add(positive, negative, dst=positive)
    cv2.bitwise_not(positive, dst=positive)
    return positive


def color_mask(image, color, threshold=30):
    """
    Create a binary mask for the pixels similar to color.

    result = 255 if diff <= threshold else 0
    where diff = sat_add(max_c(sat_sub(image - c)), max_c(sat_sub(c - image))),
    c = (r, g, b), sat_sub/sat_add are uint8 saturating ops,
    max_c takes the per-pixel maximum across channels.
    The tolerance is the same as color_similar().

    Args:
        image: Shape (height, width, channel)
        color: (r, g, b)
        threshold (int): Default to 30. Pixels with a tolerance lesser or
            equal to threshold are matched.

    Returns:
        np.ndarray: Shape (height, width), uint8, 255 for matched pixels
            and 0 for the rest.
    """
    # r, g, b = cv2.split(cv2.subtract(image, (*color, 0)))
    # positive = cv2.max(cv2.max(r, g), b)
    # r, g, b = cv2.split(cv2.subtract((*color, 0), image))
    # negative = cv2.max(cv2.max(r, g), b)
    # diff = cv2.add(positive, negative)
    # return cv2.inRange(cv2.bitwise_not(diff), 255 - threshold, 255)
    h, w = image.shape[:2]
    if h * w < 30000:
        # The 3-channel path is faster on tiny images where per-call
        # overhead dominates
        diff = cv2.subtract(image, (*color, 0))
        r, g, b = cv2.split(diff)
        cv2.max(r, g, dst=r)
        cv2.max(r, b, dst=r)
        positive = r
        cv2.subtract((*color, 0), image, dst=diff)
        r, g, b = cv2.split(diff)
        cv2.max(r, g, dst=r)
        cv2.max(r, b, dst=r)
        negative = r
        cv2.add(positive, negative, dst=positive)
        # diff is always non-negative, so 255 where diff <= threshold is
        # equivalent to inRange(255 - diff, 255 - threshold, 255) and skips
        # the intermediate bitwise_not in color_similarity_2d
        cv2.threshold(positive, threshold, 255, cv2.THRESH_BINARY_INV, dst=positive)
        return positive
    # Per-channel subtract with buffer reuse wins on larger images
    r, g, b = cv2.split(image)
    cr, cg, cb = color
    positive = cv2.subtract(r, cr)
    cv2.subtract(cr, r, dst=r)
    negative = r
    diff = cv2.subtract(g, cg)
    cv2.max(positive, diff, dst=positive)
    cv2.subtract(cg, g, dst=diff)
    cv2.max(negative, diff, dst=negative)
    cv2.subtract(b, cb, dst=diff)
    cv2.max(positive, diff, dst=positive)
    cv2.subtract(cb, b, dst=diff)
    cv2.max(negative, diff, dst=negative)
    cv2.add(positive, negative, dst=positive)
    # diff is always non-negative, so 255 where diff <= threshold is
    # equivalent to inRange(255 - diff, 255 - threshold, 255) and skips
    # the intermediate bitwise_not in color_similarity_2d
    cv2.threshold(positive, threshold, 255, cv2.THRESH_BINARY_INV, dst=positive)
    return positive


def extract_letters(image, letter=(255, 255, 255), threshold=128):
    """Set letter color to black, set background color to white.

    result = sat_mul(sat_add(max_c(sat_sub(image - l)), max_c(sat_sub(l - image))), 255 / threshold)
    where l = (r, g, b), sat_sub/sat_add/sat_mul are uint8 saturating ops,
    max_c takes the per-pixel maximum across channels, and the scale step
    is skipped when threshold = 255.
    For l = (255, 255, 255): result = sat_mul(max_c(~image), 255 / threshold).

    Args:
        image: Shape (height, width, channel)
        letter (tuple): Letter RGB.
        threshold (int):

    Returns:
        np.ndarray: Shape (height, width)
    """
    if tuple(letter) == (255, 255, 255):
        # MAX of the inverted image == inverted MIN of the image
        r, g, b = cv2.split(image)
        cv2.min(r, g, dst=r)
        cv2.min(r, b, dst=r)
        cv2.bitwise_not(r, dst=r)
        if threshold != 255:
            cv2.convertScaleAbs(r, alpha=255.0 / threshold, dst=r)
        return r
    # r, g, b = cv2.split(cv2.subtract(image, (*letter, 0)))
    # positive = cv2.max(cv2.max(r, g), b)
    # r, g, b = cv2.split(cv2.subtract((*letter, 0), image))
    # negative = cv2.max(cv2.max(r, g), b)
    # return cv2.multiply(cv2.add(positive, negative), 255.0 / threshold)
    h, w = image.shape[:2]
    if h * w < 30000:
        # The 3-channel path is faster on tiny images where per-call
        # overhead dominates
        diff = cv2.subtract(image, (*letter, 0))
        r, g, b = cv2.split(diff)
        cv2.max(r, g, dst=r)
        cv2.max(r, b, dst=r)
        positive = r
        cv2.subtract((*letter, 0), image, dst=diff)
        r, g, b = cv2.split(diff)
        cv2.max(r, g, dst=r)
        cv2.max(r, b, dst=r)
        negative = r
        if threshold != 255:
            cv2.addWeighted(positive, 255.0 / threshold, negative, 255.0 / threshold, 0, dst=positive)
        else:
            cv2.add(positive, negative, dst=positive)
        return positive
    # Per-channel subtract with buffer reuse wins on larger images
    r, g, b = cv2.split(image)
    lr, lg, lb = letter
    positive = cv2.subtract(r, lr)
    cv2.subtract(lr, r, dst=r)
    negative = r
    diff = cv2.subtract(g, lg)
    cv2.max(positive, diff, dst=positive)
    cv2.subtract(lg, g, dst=diff)
    cv2.max(negative, diff, dst=negative)
    cv2.subtract(b, lb, dst=diff)
    cv2.max(positive, diff, dst=positive)
    cv2.subtract(lb, b, dst=diff)
    cv2.max(negative, diff, dst=negative)
    if threshold != 255:
        cv2.addWeighted(positive, 255.0 / threshold, negative, 255.0 / threshold, 0, dst=positive)
    else:
        cv2.add(positive, negative, dst=positive)
    return positive


def extract_white_letters(image, threshold=128):
    """Set letter color to black, set background color to white.
    This function will discourage color pixels (Non-gray pixels)

    result = sat_mul(max' - 0.5 * min', 255 / threshold)
    where max' = max_c(255 - image) and min' = min_c(255 - image) are the
    per-pixel max/min of the inverted image across channels, and the scale
    step is skipped when threshold = 255.

    Args:
        image: Shape (height, width, channel)
        threshold (int):

    Returns:
        np.ndarray: Shape (height, width)
    """
    # r, g, b = cv2.split(cv2.subtract((255, 255, 255, 0), image))
    # minimum = cv2.min(cv2.min(r, g), b)
    # maximum = cv2.max(cv2.max(r, g), b)
    # maximum = cv2.multiply(maximum, 0.5)
    # minimum = cv2.multiply(minimum, 0.5)
    # return cv2.multiply(cv2.add(maximum, cv2.subtract(maximum, minimum)), 255.0 / threshold)
    r, g, b = cv2.split(image)
    maximum = cv2.max(r, g)
    cv2.min(r, g, dst=r)
    cv2.max(maximum, b, dst=maximum)
    cv2.min(r, b, dst=r)
    # r = MIN(r, g, b), maximum = MAX(r, g, b) in the original domain
    cv2.bitwise_not(r, dst=r)
    cv2.bitwise_not(maximum, dst=maximum)

    cv2.convertScaleAbs(r, alpha=0.5, dst=r)
    cv2.convertScaleAbs(maximum, alpha=0.5, dst=maximum)
    cv2.subtract(r, maximum, dst=maximum)
    if threshold != 255:
        cv2.addWeighted(r, 255.0 / threshold, maximum, 255.0 / threshold, 0, dst=r)
    else:
        cv2.add(r, maximum, dst=r)
    return r
