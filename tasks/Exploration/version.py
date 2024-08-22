# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2
import numpy as np

from pathlib import Path
from cached_property import cached_property

from module.base.utils import color_similarity_2d, load_image, save_image
from module.atom.gif import RuleGif
from module.atom.image import RuleImage

from tasks.base_task import BaseTask
from tasks.Exploration.assets import ExplorationAssets
from dev_tools.assets_test import detect_image


class Version(BaseTask):
    pass


def apply_mask(image, mask):
    image16 = image.astype(np.uint16)
    mask16 = mask.astype(np.uint16)
    mask16 = cv2.merge([mask16, mask16, mask16])
    image16 = cv2.multiply(image16, mask16)
    # cv2.multiply(image16, mask16, dst=image16)
    image16 = cv2.convertScaleAbs(image16, alpha=1 / 255)
    # cv2.convertScaleAbs(image16, alpha=1 / 255, dst=image16)
    # Image.fromarray(image16.astype(np.uint8)).show()
    return image16.astype(np.uint8)

def highlight(image):
    yuv = cv2.cvtColor(image, cv2.COLOR_RGB2YUV)
    _, u, _ = cv2.split(yuv)
    cv2.subtract(128, u, dst=u)
    cv2.multiply(u, 8, dst=u)

    color = color_similarity_2d(image, color=(255,255,255))
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    _, _, v = cv2.split(hsv)
    image = apply_mask(image, u)
    image = apply_mask(image, color)
    image = apply_mask(image, v)

    cv2.convertScaleAbs(image, alpha=3, dst=image)
    cv2.subtract((255, 255, 255, 0), image, dst=image)

    # from PIL import Image
    # Image.fromarray(image.astype(np.uint8)).show()
    return image


class HighlightGif(RuleGif):
    def pre_process(self, image):
        return highlight(image)

class HighLight(BaseTask, ExplorationAssets):

    @cached_property
    def TEMPLATE_GIF(self) -> RuleGif:
        return HighlightGif(
            targets=[
                self.I_LIGHT1, self.I_LIGHT2, self.I_LIGHT3, self.I_LIGHT4, self.I_LIGHT5,
                self.I_LIGHT6, self.I_LIGHT7, self.I_LIGHT8, self.I_LIGHT9, self.I_LIGHT10,
                self.I_LIGHT11, self.I_LIGHT12, self.I_LIGHT13, self.I_LIGHT14,
            ],
        )


if __name__ == '__main__':
    # image = load_image(r'C:\Users\萌萌哒\Desktop\屏幕截图 2024-08-17 175713.png')
    # image = highlight(image)
    # save_image(image, r'C:\Users\萌萌哒\Desktop\1345.png')
    #
    IMAGE_FILE = r"C:\Users\萌萌哒\Desktop\QQ20240818-163854.png"
    image = load_image(IMAGE_FILE)
    from tasks.Exploration.assets import ExplorationAssets
    targe = ExplorationAssets.I_UP_COIN
    print(targe.test_match(image))

    # from dev_tools.get_images import GetAnimation
    # from module.config.config import Config
    # from module.device.device import Device
    # c = Config('oas1')
    # d = Device(c)
    # t = HighLight(c, d)
    # t.screenshot()
    #
    # t.screenshot()
    # t.appear_then_click(t.TEMPLATE_GIF)


