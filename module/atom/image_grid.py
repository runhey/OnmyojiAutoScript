# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import numpy as np

from module.atom.image import RuleImage



class ImageGrid:

    def __init__(self, images: list[RuleImage]):
        self.images = images


    def find_anyone(self, img: np.array) -> RuleImage or None:
        """
        在这些图片中找到其中一个
        :param img:
        :return: 如果没有找到返回None
        """
        for image in self.images:
            if image.match(img):
                return image
        return None


