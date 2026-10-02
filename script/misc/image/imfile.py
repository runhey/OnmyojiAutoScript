import os

import cv2
import numpy as np

from oas.ext.path.atomic import atomic_read_bytes, atomic_write


class ImageBroken(Exception):
    """
    Raised if image failed to decode/encode
    Raised if image is empty
    """
    pass


class ImageNotSupported(Exception):
    """
    Raised if we can't perform image calculation on this image
    """
    pass


def image_channel(image) -> int:
    """
    Args:
        image (np.ndarray):

    Returns:
        int: 1 for grayscale, 3 for RGB, 4 for RGBA
    """
    shape = image.shape
    if len(shape) == 2:
        return 1
    else:
        return shape[2]


def image_size(image):
    """
    Args:
        image (np.ndarray):

    Returns:
        tuple[int, int]: width, height
    """
    shape = image.shape
    return shape[1], shape[0]


def image_shape(image):
    """
    Args:
        image (np.ndarray):

    Returns:
        tuple[int, int, int]: width, height, channel.
            channel: 1 for grayscale, 3 for RGB, 4 for RGBA
    """
    shape = image.shape
    if len(shape) == 2:
        return shape[1], shape[0], 1
    else:
        return shape[1], shape[0], shape[2]


def image_copy(src):
    """
    Equivalent to image.copy()

    Time cost to copy a 1280*720*3 image (numpy 1.24.4, opencv 4.13.0):
        src.copy()                                  0.57ms
        np.empty_like + cv2.copyTo(src, None, dst)  0.65ms
    """
    return src.copy()


def crop(image, area, copy=True):
    """
    Crop image like pillow, when using opencv / numpy.
    Provides a black background if cropping outside of image.

    Args:
        image (np.ndarray):
        area:
        copy (bool):

    Returns:
        np.ndarray:
    """
    # map(round, area)
    x1, y1, x2, y2 = area
    x1 = round(x1)
    y1 = round(y1)
    x2 = round(x2)
    y2 = round(y2)
    # h, w = image.shape[:2]
    shape = image.shape
    h = shape[0]
    w = shape[1]
    # top, bottom, left, right
    # border = np.maximum((0 - y1, y2 - h, 0 - x1, x2 - w), 0)
    overflow = False
    if y1 >= 0:
        top = 0
        if y1 >= h:
            overflow = True
    else:
        top = -y1
    if y2 > h:
        bottom = y2 - h
    else:
        bottom = 0
        if y2 <= 0:
            overflow = True
    if x1 >= 0:
        left = 0
        if x1 >= w:
            overflow = True
    else:
        left = -x1
    if x2 > w:
        right = x2 - w
    else:
        right = 0
        if x2 <= 0:
            overflow = True
    # If overflowed, return empty image
    if overflow:
        if len(shape) == 2:
            size = (y2 - y1, x2 - x1)
        else:
            size = (y2 - y1, x2 - x1, shape[2])
        return np.zeros(size, dtype=image.dtype)
    # x1, y1, x2, y2 = np.maximum((x1, y1, x2, y2), 0)
    if x1 < 0:
        x1 = 0
    if y1 < 0:
        y1 = 0
    if x2 < 0:
        x2 = 0
    if y2 < 0:
        y2 = 0
    # crop image
    image = image[y1:y2, x1:x2]
    # if border
    if top or bottom or left or right:
        if len(shape) == 2:
            value = 0
        else:
            value = tuple(0 for _ in range(image.shape[2]))
        return cv2.copyMakeBorder(image, top, bottom, left, right, borderType=cv2.BORDER_CONSTANT, value=value)
    elif copy:
        return image_copy(image)
    else:
        return image


def cvt_color_decode(image, area=None):
    """
    Convert color from opencv to RGB or grayscale

    Args:
        data (np.ndarray):
        area (tuple):

    Returns:
        np.ndarray
    """
    channel = image_channel(image)
    if area:
        # If image get cropped, return image should be copied to re-order array,
        # making later usages faster
        if channel == 3:
            # RGB
            image = crop(image, area, copy=False)
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        elif channel == 1:
            # grayscale
            return crop(image, area, copy=True)
        elif channel == 4:
            # RGBA
            image = crop(image, area, copy=False)
            return cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        else:
            raise ImageNotSupported(f'shape={image.shape}')
    else:
        if channel == 3:
            # RGB
            cv2.cvtColor(image, cv2.COLOR_BGR2RGB, dst=image)
            return image
        elif channel == 1:
            # grayscale
            return image
        elif channel == 4:
            # RGBA
            return cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        else:
            raise ImageNotSupported(f'shape={image.shape}')


def image_decode(data, area=None):
    """
    Args:
        data (np.ndarray):
        area (tuple):

    Returns:
        np.ndarray

    Raises:
        ImageBroken:
    """
    # Decode image
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ImageBroken('Empty image after cv2.imdecode')
    shape = image.shape
    if not shape:
        raise ImageBroken('Empty image after cv2.imdecode')

    return cvt_color_decode(image, area=area)


def gif_load_fframe(file, area=None):
    """
    Load the first frame of a GIF image using pure opencv.

    Args:
        file (str):
        area (tuple):

    Returns:
        np.ndarray: First frame as numpy array in RGB format

    Raises:
        FileNotFoundError:
        ImageBroken:
    """
    cap = cv2.VideoCapture(file)
    if not cap.isOpened():
        raise FileNotFoundError(f'Failed to open GIF file: {file}')

    try:
        ret, image = cap.read()
        if not ret:
            raise ImageBroken(f'Empty image after reading GIF: {file}')
        # note that VideoCapture always returns BGR/BGRA
        # if original image is in grayscale, you would get in RGB
    finally:
        cap.release()

    return cvt_color_decode(image, area=area)


def gif_load(file, area=None):
    """
    Load all frames of a GIF image using pure opencv.

    Args:
        file (str):
        area (tuple):

    Returns:
        list[np.ndarray]: List of frames as numpy array in RGB format

    Raises:
        FileNotFoundError:
        ImageBroken:
    """
    cap = cv2.VideoCapture(file)
    if not cap.isOpened():
        raise FileNotFoundError(f'Failed to open GIF file: {file}')

    frames = []
    try:
        while 1:
            ret, image = cap.read()
            if not ret:
                break
            # note that VideoCapture always returns BGR/BGRA
            # if original image is in grayscale, you would get in RGB
            image = cvt_color_decode(image, area=area)
            frames.append(image)
    finally:
        cap.release()
    if not frames:
        raise ImageBroken(f'Empty image after reading GIF: {file}')

    return frames


def image_load(file, area=None):
    """
    Load an image using pure opencv and drop alpha channel.
    If file is gif, will only read first frame

    Args:
        file (str):
        area (tuple):

    Returns:
        np.ndarray:

    Raises:
        FileNotFoundError:
        ImageBroken:
    """
    if file.endswith('.gif'):
        return gif_load_fframe(file, area=area)
    # cv2.imread can't handle non-ascii filepath and PIL.Image.open is slow
    # Here we read with numpy first
    # may raise FileNotFoundError
    content = atomic_read_bytes(file)
    data = np.frombuffer(content, dtype=np.uint8)
    if not data.size:
        raise ImageBroken(f'Image with size=0: {file}')
    return image_decode(data, area=area)


def cvt_color_encode(image):
    """
    Convert color from RGB or grayscale to opencv

    Args:
        data (np.ndarray):

    Returns:
        np.ndarray
    """
    channel = image_channel(image)
    if channel == 3:
        # RGB
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    elif channel == 1:
        # grayscale, keep grayscale unchanged
        return image
    elif channel == 4:
        # RGBA
        return cv2.cvtColor(image, cv2.COLOR_RGBA2BGRA)
    else:
        raise ImageNotSupported(f'shape={image.shape}')


def image_encode(image, ext='png', encode=None):
    """
    Encode image
    Note that if you need bytes output, do "data.tobytes()"

    Args:
        image (np.ndarray):
        ext:
        encode (list): Extra encode options

    Returns:
        np.ndarray:
    """
    # Prepare encode params
    ext = ext.lower()
    if encode is None:
        if ext == 'png':
            # Best compression, 0~9
            encode = [cv2.IMWRITE_PNG_COMPRESSION, 9]
        elif ext == 'jpg' or ext == 'jpeg':
            # Best quality
            encode = [cv2.IMWRITE_JPEG_QUALITY, 100]
        elif ext.lower() == 'webp':
            # 0~100 is lossy, >100 is lossless
            encode = [cv2.IMWRITE_WEBP_QUALITY, 101]
        elif ext == 'tiff' or ext == 'tif':
            # LZW compression in TIFF
            encode = [cv2.IMWRITE_TIFF_COMPRESSION, 5]
        else:
            raise ImageNotSupported(f'Unsupported file extension "{ext}"')

    # Encode
    image = cvt_color_encode(image)
    ret, buf = cv2.imencode(f'.{ext}', image, encode)
    if not ret:
        raise ImageBroken('cv2.imencode failed')

    return buf


def image_save(file, image, encode=None, skip_same=False):
    """
    Save an image using pure opencv

    Args:
        file (str):
        image (np.ndarray):
        encode: (list): Encode params
        skip_same (bool):
            True to skip writing if existing content is the same as content to write.
            This would reduce disk write but add disk read

    Returns:
        bool: if write
    """
    _, _, ext = file.rpartition('.')
    data = image_encode(image, ext=ext, encode=encode).tobytes()
    if skip_same:
        try:
            old = atomic_read_bytes(file)
            if data == old:
                return False
        except FileNotFoundError:
            pass

    atomic_write(file, data)
    return True


def image_fixup(file, need_crop=False):
    """
    Save image using opencv again, making it smaller and shutting up libpng
    libpng warning: iCCP: known incorrect sRGB profile
    libpng warning: iCCP: cHRM chunk does not match sRGB
    libpng warning: sBIT: invalid

    Args:
        file (str):
        need_crop (bool): True to fixup cropped only and ignore full screenshots

    Returns:
        bool: If file changed
    """
    _, _, ext = file.rpartition('.')

    # image_load
    try:
        content = atomic_read_bytes(file)
    except FileNotFoundError:
        # File not exist, no need to fixup
        return False
    data = np.frombuffer(content, dtype=np.uint8)
    if not data.size:
        return False
    try:
        image = image_decode(data)
    except ImageBroken:
        # Ignore error because truncated image don't need fixup
        return False

    if need_crop:
        from script.misc.image.draw import get_bbox
        try:
            bbox = get_bbox(image)
        except ImageNotSupported:
            return False
        w, h = image_size(image)
        if bbox == (0, 0, w, h):
            return False

    # image_save
    try:
        data = image_encode(image, ext=ext)
    except ImageBroken:
        # Ignore error because truncated image don't need fixup
        return False

    # Convert numpy array to bytes is slower than directly writing into file
    # but here we want to compare before and after
    new_content = data.tobytes()
    if content != new_content:
        atomic_write(file, new_content)
        return True
    else:
        # Same as before, no need to write
        return False


def image_fixup_any(path):
    """
    Fixup a file or a directory of files
    Note that this function should only be used in develop environment.

    Args:
        path (str): If path is a directory fixup .png files recursively,
            otherwise fixup this image only.

    Returns:
        int: Amount of fixed up images
    """
    # Fixup image directly
    if path.endswith('.png'):
        if image_fixup(path):
            return 1
        else:
            return 0
    # If path is a directory fixup .png files recursively
    if os.path.isdir(path):
        count = 0
        # Local import
        from oas.ext.path.iter import iter_files
        files = iter_files(path, ext='.png', recursive=True)
        for file in files:
            if image_fixup(file):
                count += 1
        return count
    # Proceed as image anyway
    if image_fixup(path):
        return 1
    else:
        return 0
