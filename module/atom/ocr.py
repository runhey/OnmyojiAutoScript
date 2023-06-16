# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey


import cv2

from module.ocr.base_ocr import BaseCor, OcrMode, OcrMethod
from module.ocr.sub_ocr import Full, SingleLine, Digit, DigitCounter, Duration
from module.logger import logger



class RuleOcr(Full, SingleLine, Digit, DigitCounter, Duration):

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

