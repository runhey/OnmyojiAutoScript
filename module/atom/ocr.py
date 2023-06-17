# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey


import cv2

from module.ocr.base_ocr import BaseCor, OcrMode, OcrMethod
from module.ocr.sub_ocr import Full, Single, Digit, DigitCounter, Duration
from module.logger import logger



class RuleOcr(Full, Single, Digit, DigitCounter, Duration):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def after_process(self, result):
        match self.mode:
            case OcrMode.FULL: return Full.after_process(self, result)
            case OcrMode.SINGLE: return Single.after_process(self, result)
            case OcrMode.DIGIT: return Digit.after_process(self, result)
            case OcrMode.DIGIT_COUNTER: return DigitCounter.after_process(self, result)
            case OcrMode.DURATION: return Duration.after_process(self, result)
            case _: return result

    def ocr(self, image, keyword=None):

        match self.mode:
            case OcrMode.FULL: return Full.ocr_full(self, image, keyword)
            case OcrMode.SINGLE: return Single.ocr_single_line(self, image)
            case OcrMode.DIGIT: return Digit.ocr_digit(self, image)
            case OcrMode.DIGIT_COUNTER: return DigitCounter.ocr_digit_counter(self, image)
            case OcrMode.DURATION: return Duration.ocr_duration(self, image)
            case _: return None



if __name__ == "__main__":
    o = RuleOcr("ocr", "Single", "Default", (1, 2, 3, 4), (1, 2, 3, 4), "keyword")

