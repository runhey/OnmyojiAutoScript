import cv2

from script.misc.image.imfile import ImageNotSupported, image_channel, image_copy, image_size


def show_as_pillow(image):
    """
    Show image in Pillow, for debugging purpose
    """
    channel = image_channel(image)
    from PIL import Image
    if channel == 3:
        Image.fromarray(image, mode='RGB').show()
    elif channel == 1:
        Image.fromarray(image, mode='L').show()
    elif channel == 4:
        Image.fromarray(image, mode='RGBA').show()
    else:
        raise ImageNotSupported(f'shape={image.shape}')


def resize(image, size):
    """
    Resize image like pillow image.resize(), but implement in opencv.
    Pillow uses PIL.Image.NEAREST by default.

    Args:
        image (np.ndarray):
        size: (x, y)

    Returns:
        np.ndarray:
    """
    return cv2.resize(image, size, interpolation=cv2.INTER_NEAREST)


def resize_maxpx(image, maxpx):
    """
    Resize image to maximum width or height

    Args:
        image (np.ndarray):
        maxpx: Maximum width or height

    Returns:
        np.ndarray:
    """
    w, h = image_size(image)
    if w <= maxpx and h <= maxpx:
        # no need to resize
        return image

    if w > h:
        h = round(maxpx / w * h)
        w = maxpx
    else:
        w = round(maxpx / h * w)
        h = maxpx

    return cv2.resize(image, (w, h), interpolation=cv2.INTER_NEAREST)


def image_paste(image, background, origin):
    """
    Paste an image on background.
    This method does not return a value, but instead updates the array "background".

    Args:
        image (np.ndarray):
        background:
        origin: Upper-left corner, (x, y)
    """
    if not image.flags.writeable:
        image = image_copy(image)

    x, y = origin
    w, h = image_size(image)
    background[y:y + h, x:x + w] = image


def image_paint(image, area, color):
    """
    Paint the area of image to given color

    Args:
        image (np.ndarray):
        area:
        color: (r, g, b) or value if grayscale
    """
    if not image.flags.writeable:
        image = image_copy(image)

    x1, y1, x2, y2 = area
    image[y1:y2, x1:x2] = color


def image_paint_white(image, area):
    """
    Paint the area of image to black

    Args:
        image (np.ndarray):
        area:
    """
    if not image.flags.writeable:
        image = image_copy(image)

    channel = image_channel(image)
    x1, y1, x2, y2 = area
    if channel == 3:
        # RGB
        image[y1:y2, x1:x2] = (255, 255, 255)
    elif channel == 1:
        # grayscale
        image[y1:y2, x1:x2] = 255
    elif channel == 4:
        # RGBA
        image[y1:y2, x1:x2] = (255, 255, 255, 255)
    else:
        # ImageNotSupported, but we can still paint
        color = tuple([255] * channel)
        image[y1:y2, x1:x2] = color
    return image


def image_paint_black(image, area):
    """
    Paint the area of image to black

    Args:
        image (np.ndarray):
        area:
    """
    if not image.flags.writeable:
        image = image_copy(image)

    channel = image_channel(image)
    x1, y1, x2, y2 = area
    if channel == 3:
        # RGB
        image[y1:y2, x1:x2] = (0, 0, 0)
    elif channel == 1:
        # grayscale
        image[y1:y2, x1:x2] = 0
    elif channel == 4:
        # RGBA
        image[y1:y2, x1:x2] = (0, 0, 0, 255)
    else:
        # ImageNotSupported, but we can still paint
        color = tuple([0] * channel)
        image[y1:y2, x1:x2] = color
    return image


def get_bbox(image, threshold=0):
    """
    Get outbound box of the content in image
    A opencv implementation of the getbbox() in pillow

    Args:
        image (np.ndarray):
        threshold (int):
            color > threshold will be considered as content
            color <= threshold will be considered background

    Returns:
        tuple[int, int, int, int]: area

    Raises:
        ImageNotSupported: if failed to get bbox
    """
    channel = image_channel(image)
    # convert to grayscale
    if channel == 3:
        # RGB
        mask = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        cv2.threshold(mask, threshold, 255, cv2.THRESH_BINARY, dst=mask)
    elif channel == 1:
        # grayscale
        _, mask = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY)
    elif channel == 4:
        # RGBA
        mask = cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)
        cv2.threshold(mask, threshold, 255, cv2.THRESH_BINARY, dst=mask)
    else:
        raise ImageNotSupported(f'shape={image.shape}')

    # find bbox
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_y, min_x = mask.shape
    max_x = 0
    max_y = 0
    # all black
    if not contours:
        raise ImageNotSupported(f'Cannot get bbox from a pure black image')
    for contour in contours:
        # x, y, w, h
        x1, y1, x2, y2 = cv2.boundingRect(contour)
        x2 += x1
        y2 += y1
        if x1 < min_x:
            min_x = x1
        if y1 < min_y:
            min_y = y1
        if x2 > max_x:
            max_x = x2
        if y2 > max_y:
            max_y = y2
    if min_x < max_x and min_y < max_y:
        return min_x, min_y, max_x, max_y
    else:
        # This shouldn't happen
        raise ImageNotSupported(f'Empty bbox {(min_x, min_y, max_x, max_y)}')


def get_bbox_reversed(image, threshold=255):
    """
    Get outbound box of the content in image
    A opencv implementation of the getbbox() in pillow

    Args:
        image (np.ndarray):
        threshold (int):
            color < threshold will be considered as content
            color >= threshold will be considered background

    Returns:
        tuple[int, int, int, int]: area

    Raises:
        ImageNotSupported: if failed to get bbox
    """
    channel = image_channel(image)
    # convert to grayscale
    if channel == 3:
        # RGB
        mask = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        cv2.threshold(mask, 0, threshold, cv2.THRESH_BINARY, dst=mask)
    elif channel == 1:
        # grayscale
        _, mask = cv2.threshold(image, 0, threshold, cv2.THRESH_BINARY)
    elif channel == 4:
        # RGBA
        mask = cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)
        cv2.threshold(mask, 0, threshold, cv2.THRESH_BINARY, dst=mask)
    else:
        raise ImageNotSupported(f'shape={image.shape}')

    # find bbox
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_y, min_x = mask.shape
    max_x = 0
    max_y = 0
    # all black
    if not contours:
        raise ImageNotSupported(f'Cannot get bbox from a pure black image')
    for contour in contours:
        # x, y, w, h
        x1, y1, x2, y2 = cv2.boundingRect(contour)
        x2 += x1
        y2 += y1
        if x1 < min_x:
            min_x = x1
        if y1 < min_y:
            min_y = y1
        if x2 > max_x:
            max_x = x2
        if y2 > max_y:
            max_y = y2
    if min_x < max_x and min_y < max_y:
        return min_x, min_y, max_x, max_y
    else:
        # This shouldn't happen
        raise ImageNotSupported(f'Empty bbox {(min_x, min_y, max_x, max_y)}')
