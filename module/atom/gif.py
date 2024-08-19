# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import numpy as np

from module.atom.image import RuleImage



class RuleGif:
    # 大部分实现同RuleImage 的接口

    @property
    def name(self) -> str:
        return self.appear_target.name

    def __init__(self, targets: list[RuleImage]):
        self.targets = targets
        self.roi_front: list = [0, 0, 0, 0]
        self.appear_target = targets[0]

    def pre_process(self, image):
        return image


    def search(self, image, roi: list = None, threshold: float = None) -> tuple:
        """

        :param image:
        :param roi:
        :param threshold:
        :return: bool
        第一项是否为出现, 第二项为匹配的RuleImage
        """
        image = self.pre_process(image)
        #
        threshold = self.targets[0].threshold if threshold is None else threshold
        roi = self.targets[0].roi_back if roi is None else roi
        for target in self.targets:
            target.roi_back = roi
            if target.match(image, threshold):
                self.roi_front = target.roi_front
                self.appear_target = target
                return True, target
        return False, None

    def match(self, image, threshold: float = None) -> bool:
        return self.search(image, threshold=threshold)[0]


    def coord(self) -> tuple:
        x, y, w, h = self.roi_front
        return x + np.random.randint(0, w), y + np.random.randint(0, h)

    def front_center(self) -> tuple:
        x, y, w, h = self.roi_front
        return int(x + w//2), int(y + h//2)
