import os

import cv2
import numpy as np
from PIL import Image

from script.misc.image.imfile import ImageNotSupported, image_channel
from oas.ext.path.atomic import replace_tmp, to_tmp_file
from oas.ext.path.calc import get_suffix


def image_load_pillow(file, area=None):
    """
    Load an image using pillow and drop alpha channel.
    Note that pillow methods are slower than opencv, you should use image_load() in production

    Args:
        file (str):
        area (tuple):

    Returns:
        np.ndarray:

    Raises:
        FileNotFoundError:
        ImageBroken:
    """
    # always remember to close Image object
    with Image.open(file) as f:
        if area is not None:
            f = f.crop(area)

        image = np.array(f)

    channel = image_channel(image)
    if channel == 4:
        image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)

    return image


def image_save_pillow(file, image):
    """
    Save an image using pillow
    Note that:
        pillow methods are slower than opencv, you should use image_save() in production.
        if you write files using pillow, libpng will spam warnings when re-reading it

    Args:
        file (str):
        image (np.ndarray):

    Returns:
        bool: if write
    """
    channel = image_channel(image)
    if channel == 3:
        mode = 'RGB'
    elif channel == 1:
        mode = 'L'
    elif channel == 4:
        mode = 'RGBA'
    else:
        raise ImageNotSupported(f'shape={image.shape}')

    # encode
    im = Image.fromarray(image, mode=mode)

    ext = get_suffix(file).lower().lstrip('.')
    tmp = to_tmp_file(file)

    try:
        # Write temp file
        im.save(tmp, format=ext)
    except FileNotFoundError:
        pass
    else:
        replace_tmp(tmp, file)
        return True

    # Create parent directory
    directory = os.path.dirname(file)
    if directory:
        os.makedirs(directory, exist_ok=True)
    # Write again
    im.save(tmp, format=ext)
    replace_tmp(tmp, file)
    return True
