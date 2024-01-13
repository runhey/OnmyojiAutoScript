import cv2
import numpy as np

from numpy import float32, int32, uint8, fromfile
from pathlib import Path

from module.logger import logger
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr


def load_image(file: str):
    img = cv2.imdecode(fromfile(file, dtype=uint8), -1)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    height, width, channels = img.shape
    if height != 720 or width != 1280:
        logger.error(f'Image size is {height}x{width}, not 720x1280')
        return None
    return img


def detect_image(file: str, targe: RuleImage) -> bool:
    img = load_image(file)
    return targe.match(img)


# 图片文件路径 可以是相对路径
IMAGE_FILE = './log/error/1704971960417/2024-01-11_19-19-20-403213.png'
if __name__ == '__main__':
    from tasks.KekkaiActivation.assets import KekkaiActivationAssets
    targe = KekkaiActivationAssets.I_A_HARVEST_FISH_6
    print(detect_image(IMAGE_FILE, targe))



