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
        self._kp = None  #
        self._des = None
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

    def load_kp_des(self) -> None:
        if self._kp is not None and self._des is not None:
            return
        self._kp, self._des = self.sift.detectAndCompute(self.image, None)


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

    @cached_property
    def is_sift_flann(self) -> bool:
        return self.method == "Sift Flann"

    @cached_property
    def sift(self):
        return cv2.SIFT_create()

    @cached_property
    def kp(self):
        if self._kp is None:
            self.load_kp_des()
        return self._kp

    @cached_property
    def des(self):
        if self._des is None:
            self.load_kp_des()
        return self._des

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

    def test_match(self, image: np.array):
        if self.is_template_match:
            return self.match(image)
        if self.is_sift_flann:
            return self.sift_match(image, show=True)

    def sift_match(self, image: np.array, show=False) -> bool:
        """
        特征匹配，同样会修改 roi_front
        :param image: 是游戏的截图，就是转通道后的截图
        :param show: 测试用的
        :return:
        """
        source = self.corp(image)
        kp, des = self.sift.detectAndCompute(source, None)
        # 参数1：index_params
        #    对于SIFT和SURF，可以传入参数index_params=dict(algorithm=FLANN_INDEX_KDTREE, trees=5)。
        #    对于ORB，可以传入参数index_params=dict(algorithm=FLANN_INDEX_LSH, table_number=6, key_size=12）。
        index_params = dict(algorithm=1, trees=5)
        # 参数2：search_params 指定递归遍历的次数，值越高结果越准确，但是消耗的时间也越多。
        search_params = dict(checks=50)
        # 根据设置的参数创建特征匹配器 指定匹配的算法和kd树的层数,指定返回的个数
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        # 利用创建好的特征匹配器利用k近邻算法来用模板的特征描述符去匹配图像的特征描述符，k指的是返回前k个最匹配的特征区域
        # 返回的是最匹配的两个特征点的信息，返回的类型是一个列表，列表元素的类型是Dmatch数据类型，具体是什么我也不知道
        # 第一个参数是小图的des, 第二个参数是大图的des
        matches = flann.knnMatch(self.des, des, k=2)

        good = []
        result = True
        for i, (m, n) in enumerate(matches):
            # 设定阈值, 距离小于对方的距离的0.7倍我们认为是好的匹配点.
            if m.distance < 0.6 * n.distance:
                good.append(m)
        if len(good) >= 4:
            src_pts = float32([self.kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = float32([kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

            # 计算透视变换矩阵m， 要求点的数量>=4
            m, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            # 创建一个包含模板图像四个角坐标的数组
            w, h = self.roi_front[2], self.roi_front[3]
            pts = float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
            if m is None:
                result = False
            else:
                dst = int32(cv2.perspectiveTransform(pts, m))
                self.roi_front[0] = dst[0, 0, 0] + self.roi_back[0]
                self.roi_front[1] = dst[0, 0, 1] + self.roi_back[1]
                if show:
                    cv2.polylines(source, [dst], isClosed=True, color=(0, 0, 255), thickness=2)
        else:
            result = False

        # https://blog.csdn.net/cungudafa/article/details/105399278
        # https://blog.csdn.net/qq_45832961/article/details/122776322
        if show:
            # 准备一个空的掩膜来绘制好的匹配
            mask_matches = [[0, 0] for i in range(len(matches))]
            # 向掩膜中添加数据
            for i, (m, n) in enumerate(matches):
                if m.distance < 0.6 * n.distance:  # 理论上0.7最好
                    mask_matches[i] = [1, 0]
            img_matches = cv2.drawMatchesKnn(self.image, self.kp, source, kp, matches, None,
                                             matchColor=(0, 255, 0), singlePointColor=(255, 0, 0),
                                             matchesMask=mask_matches, flags=0)
            cv2.imshow(f'Sift Flann: {self.name}', img_matches)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        return result


if __name__ == "__main__":
    from dev_tools.assets_test import detect_image

    IMAGE_FILE = './log/test/QQ截图20240223151924.png'
    from tasks.Restart.assets import RestartAssets
    jade = RestartAssets.I_HARVEST_JADE
    jade.method = 'Sift Flann'
    sign = RestartAssets.I_HARVEST_SIGN
    sign.method = 'Sift Flann'
    print(jade.roi_front)

    detect_image(IMAGE_FILE, jade)
    detect_image(IMAGE_FILE, sign)
    print(jade.roi_front)

