# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
import cv2
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
    SINGLE_LINE = 2  # str: "SingleLine"
    DIGIT = 3  # str: "Digit"
    DIGIT_COUNTER = 4  # str: "DigitCounter"
    DURATION = 5  # str: "Duration"

class OcrMethod(Enum):
    DEFAULT = 1  # str: "Default"

class BaseCor:

    lang: str = "cn"
    score: float = 0.5  # 阈值默认为0.5

    name: str = "ocr"
    mode: OcrMode = OcrMode.FULL
    method: OcrMethod = OcrMethod.DEFAULT  # 占位符
    roi: list = []  # [x, y, width, height]
    area: list = []  # [x, y, width, height]
    keyword: str = ""  # 默认为空

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

    def ocr_single_line(self, image):
        """
        只支持横方向的单行ocr，不支持竖方向的单行ocr
        注意：这里使用了预处理和后处理
        :param image:
        :return:
        """
        # pre process
        start_time = time.time()
        image = crop(image, self.roi, copy=False)
        image = self.pre_process(image)
        # ocr
        result, _ = self.model.ocr_single_line(image)
        # after proces
        result = self.after_process(result)
        logger.attr(name='%s %ss' % (self.name, float2str(time.time() - start_time)),
                    text=str(result))
        return result

    def detect_and_ocr(self, image) -> list[BoxedResult]:
        """
        注意：这里使用了预处理和后处理
        :param image:
        :return:
        """
        # pre process
        start_time = time.time()
        image = self.pre_process(image)
        # ocr
        results: list[BoxedResult] = self.model.detect_and_ocr(image)
        # after proces
        for result in results:
            result.ocr_text = self.after_process(result.ocr_text)

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


