# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

import numpy as np
import cv2

from module.ocr.base_ocr import BaseCor, OcrMode, OcrMethod
from module.ocr.sub_ocr import Full, Single, Digit, DigitCounter, Duration
from module.logger import logger



class RuleOcr(Digit, DigitCounter, Duration, Single, Full):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def after_process(self, result):
        match self.mode:
            case OcrMode.FULL: return Full.after_process(self, result)
            case OcrMode.SINGLE: return Single.after_process(self, result)
            case OcrMode.DIGIT: return Digit.after_process(self, result)
            case OcrMode.DIGITCOUNTER: return DigitCounter.after_process(self, result)
            case OcrMode.DURATION: return Duration.after_process(self, result)
            case _: return result

    def ocr(self, image, keyword=None):

        match self.mode:
            case OcrMode.FULL: return Full.ocr_full(self, image, keyword)
            case OcrMode.SINGLE: return Single.ocr_single(self, image)
            case OcrMode.DIGIT: return Digit.ocr_digit(self, image)
            case OcrMode.DIGITCOUNTER: return DigitCounter.ocr_digit_counter(self, image)
            case OcrMode.DURATION: return Duration.ocr_duration(self, image)
            case _: return None

    def coord(self) -> tuple:
        """
        获取一个区域，随机返回一个坐标
        :return:
        """
        area = None
        if self.mode == OcrMode.FULL:
            area = self.area
        else:
            area = self.roi

        x, y, w, h = self.area
        x = np.random.randint(x, x + w)
        y = np.random.randint(y, y + h)
        return x, y



if __name__ == "__main__":
    pass

