# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2
import numpy as np

from numpy import float32, int32, uint8, fromfile
from pathlib import Path

from module.base.decorator import cached_property
from module.logger import logger

class RuleImage:

    def __init__(self, roi_front: tuple, roi_back: tuple, method: str, threshold: float, file: str) -> None:
        """
        初始化
        :param roi_front: 前置roi
        :param roi_back: 后置roi 用于匹配的区域
        :param method: 匹配方法 "Template matching"
        :param threshold: 阈值  0.8
        :param file: 相对路径, 带后缀
        """
        self._match_init = False  # 这个是给后面的 等待图片稳定
        self._image = None  # 这个是匹配的目标
        self.method = method

        self.roi_front: list = list(roi_front)
        self.roi_back = roi_back
        self.threshold = threshold
        self.file = file



    @cached_property
    def name(self) -> str:
        """

        :return:
        """
        return Path(self.file).stem.upper()

    def __str__(self):
        return self.name

    __repr__ = __str__

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self.name)

    def __bool__(self):
        return True



    def load_image(self) -> None:
        """
        加载图片
        :return:
        """
        if self._image is not None:
            return
        img = cv2.imdecode(fromfile(self.file, dtype=uint8), -1)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self._image = img

        height, width, channels = self._image.shape
        if height != self.roi_front[3] or width != self.roi_front[2]:
            self.roi_front[2] = width
            self.roi_front[3] = height
            logger.info(f"roi_front size changed to {width}x{height}")

    @property
    def image(self):
        """
        获取图片
        :return:
        """
        if self._image is None:
            self.load_image()
        return self._image

    @cached_property
    def is_template_match(self) -> bool:
        """
        是否是模板匹配
        :return:
        """
        return self.method == "Template matching"

    def corp(self, image: np.array) -> np.array:
        """
        截取图片
        :param image:
        :return:
        """
        x, y, w, h = self.roi_back
        x, y, w, h = int(x), int(y), int(w), int(h)
        return image[y:y + h, x:x + w]

    def match(self, image: np.array, threshold: float = None) -> bool:
        """
        :param threshold:
        :param image:
        :return:
        """
        if threshold is None:
            threshold = self.threshold

        if not self.is_template_match:
            raise Exception(f"unknown method {self.method}")

        source = self.corp(image)
        mat = self.image
        res = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)  # 最小匹配度，最大匹配度，最小匹配度的坐标，最大匹配度的坐标
        # logger.attr(self.name, max_val)
        if max_val > threshold:
            self.roi_front[0] = max_loc[0] + self.roi_back[0]
            self.roi_front[1] = max_loc[1] + self.roi_back[1]
            return True
        else:
            return False

    def coord(self) -> tuple:
        """
        获取roi_front的随机的点击的坐标
        :return:
        """
        x, y, w, h = self.roi_front
        return x + np.random.randint(0, w), y + np.random.randint(0, h)

    def coord_more(self) -> tuple:
        """
         获取roi_back的随机的点击的坐标
        :return:
        """
        x, y, w, h = self.roi_back
        return x + np.random.randint(0, w), y + np.random.randint(0, h)

    def front_center(self) -> tuple:
        """
        获取roi_front的中心坐标
        :return:
        """
        x, y, w, h = self.roi_front
        return int(x + w//2), int(y + h//2)



if __name__ == "__main__":
    image = cv2.imread("D:/4713.jpg")
    mat = RuleImage(roi_front=(758,122,66,77), roi_back=(339,104,836,120), threshold=0.8, method="Template matching", file="./tasks/AreaBoss/res/res_explore.png")
    print(mat.match(image))
