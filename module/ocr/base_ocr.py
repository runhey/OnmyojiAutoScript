# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
import cv2
import numpy as np

from ppocronnx.predict_system import BoxedResult
from enum import Enum


from module.base.decorator import cached_property
from module.base.utils import area_pad, crop, float2str
from module.ocr.ppocr import TextSystem
from module.ocr.models import OCR_MODEL
from module.exception import ScriptError
from module.logger import logger


class OcrMode(Enum):
    FULL = 1  # str: "Full"
    SINGLE = 2  # str: "Single"
    DIGIT = 3  # str: "Digit"
    DIGITCOUNTER = 4  # str: "DigitCounter"
    DURATION = 5  # str: "Duration"

class OcrMethod(Enum):
    DEFAULT = 1  # str: "Default"

class BaseCor:

    lang: str = "ch"
    score: float = 0.6  # 阈值默认为0.5

    name: str = "ocr"
    mode: OcrMode = OcrMode.FULL
    method: OcrMethod = OcrMethod.DEFAULT  # 占位符
    roi: list = []  # [x, y, width, height]
    area: list = []  # [x, y, width, height]
    keyword: str = ""  # 默认为空


    def __init__(self,
                 name: str,
                 mode: str,
                 method: str,
                 roi: tuple,
                 area: tuple,
                 keyword: str) -> None:
        """

        :param name:
        :param mode:
        :param method:
        :param roi:
        :param area:
        :param keyword:
        """
        self.name = name
        if isinstance(mode, str):
            self.mode = OcrMode[mode.upper()]
        elif isinstance(mode, OcrMode):
            self.mode = mode
        if isinstance(method, str):
            self.method = OcrMethod[method.upper()]
        elif isinstance(method, OcrMethod):
            self.method = method
        self.roi: list = list(roi)
        self.area: list = list(area)
        self.keyword = keyword

    @cached_property
    def model(self) -> TextSystem:
        return OCR_MODEL.__getattribute__(self.lang)

    def pre_process(self, image):
        """
        重写
        :param image:
        :return:
        """
        return image

    def after_process(self, result):
        """
        重写
        :param result:
        :return:
        """
        return result

    @classmethod
    def crop(cls, image: np.array, roi: tuple) -> np.array:
        """
        截取图片
        :param roi:
        :param image:
        :return:
        """
        x, y, w, h = roi
        return image[y:y + h, x:x + w]

    def ocr_item(self, image):
        """
        这个函数区别于ocr_single_line，这个函数不对图片进行裁剪，是什么就是什么的
        :param image:
        :return:
        """
        # pre process
        start_time = time.time()
        image = self.pre_process(image)
        # ocr
        result, score = self.model.ocr_single_line(image)
        if score < self.score:
            result = ""
        # after proces
        result = self.after_process(result)
        logger.info("ocr result score: %s%s" % (result,score))
        logger.attr(name='%s %ss' % (self.name, float2str(time.time() - start_time)),
                    text=f'[{result}]')
        return result

    def ocr_single_line(self, image):
        """
        只支持横方向的单行ocr，不支持竖方向的单行ocr
        注意：这里使用了预处理和后处理
        :param image:
        :return:
        """
        # pre process
        start_time = time.time()
        image = self.crop(image, self.roi)
        image = self.pre_process(image)
        # ocr
        result, score = self.model.ocr_single_line(image)
        if score < self.score:
            result = ""
        # after proces
        result = self.after_process(result)
        logger.info("ocr result score: %s" % score)
        logger.attr(name='%s %ss' % (self.name, float2str(time.time() - start_time)),
                    text=f'[{result}]')
        return result

    def detect_and_ocr(self, image) -> list[BoxedResult]:
        """
        注意：这里使用了预处理和后处理
        :param image:
        :return:
        """
        # pre process
        start_time = time.time()
        image = self.crop(image, self.roi)
        image = self.pre_process(image)

        # ocr
        boxed_results: list[BoxedResult] = self.model.detect_and_ocr(image)
        results = []
        # after proces
        for result in boxed_results:
            logger.info("ocr result score: %s" % result.score)
            if result.score < self.score:
                continue
            result.ocr_text = self.after_process(result.ocr_text)
            results.append(result)

        logger.attr(name='%s %ss' % (self.name, float2str(time.time() - start_time)),
                    text=str([result.ocr_text for result in results]))
        return results

    def match(self, result: str, included: bool=False) -> bool:
        """
        使用ocr获取结果后和keyword进行匹配
        :param result:
        :param included:  ocr结果和keyword是否包含关系, 要么是包含关系，要么是相等关系
        :return:
        """
        if included:
            return self.keyword in result
        else:
            return self.keyword == result


    def filter(self, boxed_results: list[BoxedResult], keyword: str=None) -> list:
        """
        使用ocr获取结果后和keyword进行匹配. 返回匹配的index list
        :param keyword: 如果不指定默认适用对象的keyword
        :param boxed_results:
        :return:
        """
        # 首先先将所有的ocr的str顺序拼接起来, 然后再进行匹配
        result = None
        strings = [boxed_result.ocr_text for boxed_result in boxed_results]
        concatenated_string = "".join(strings)
        if keyword is None:
            keyword = self.keyword
        if keyword in concatenated_string:
            result = [index for index, _ in enumerate(strings)]
        else:
            result = None

        if result is not None:
            # logger.info("Filter result: %s" % result)
            return result

        # 如果适用顺序拼接还是没有匹配到，那可能是竖排的，使用单个字节的keyword进行匹配
        indices = []
        for index, char in enumerate(keyword):
            for i, string in enumerate(strings):
                if char not in string:
                    break
                if i == len(strings) - 1:
                    indices.append(index)
        if indices:
            return indices
        else:
            indices = None
            return indices


