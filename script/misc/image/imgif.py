import os

import cv2
import imageio

from script.misc.image.imfile import crop, image_channel
from oas.ext.path.atomic import replace_tmp, to_tmp_file
from oas.ext.path.calc import get_suffix


def gif_load_imageio(file, area=None):
    """
    Load an image using imageio and drop alpha channel.
    Note that imageio methods are slower than opencv, you should use gif_load() in production

    Args:
        file (str):
        area (tuple):

    Returns:
        list[np.ndarray]: List of frames

    Raises:
        FileNotFoundError:
        ImageBroken:
    """
    frames = []
    for image in imageio.mimread(file):
        channel = image_channel(image)
        if area:
            if channel == 4:
                # RGBA
                image = crop(image, area, copy=False)
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            else:
                image = crop(image, area, copy=True)
        else:
            if channel == 4:
                # RGBA
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            else:
                pass

        frames.append(image)

    return frames


# Alright I just don't wanna import packaging, simple version compare should work
version = tuple(int(semi) if semi.isdigit() else semi for semi in imageio.__version__.split('.'))
if version >= (2, 21, 3):
    # since https://github.com/imageio/imageio/releases/tag/v2.21.3 mimsave(fps=...) is not allowed,
    # so we convert it
    def mimsave(uri, ims, format=None, **kwargs):
        fps = kwargs.pop('fps', None)
        if fps:
            kwargs['duration'] = 1000 / fps
        return imageio.mimsave(uri, ims, format=format, **kwargs)
else:
    mimsave = imageio.mimsave


def gif_save_imageio(frames, file, fps=5):
    """
    Save an image using imageio
    Note that opencv is poor on writing GIF, this method is the only way to write GIF.

    Args:
        frames (list[np.ndarray]):
        file (str):
        fps (int | float):
    """
    ext = get_suffix(file).lower().lstrip('.')
    tmp = to_tmp_file(file)

    try:
        # Write temp file
        mimsave(tmp, frames, format=ext, fps=fps)
    except FileNotFoundError:
        pass
    else:
        replace_tmp(tmp, file)
        return

    # Create parent directory
    directory = os.path.dirname(file)
    if directory:
        os.makedirs(directory, exist_ok=True)
    # Write again
    mimsave(tmp, frames, format=ext, fps=fps)
    replace_tmp(tmp, file)
