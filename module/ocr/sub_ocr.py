# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

import cv2
from module.ocr.ppocr import TextSystem
from module.exception import ScriptError
from module.ocr.base_ocr import BaseCor, OcrMode, OcrMethod
from module.logger import logger


class Full(BaseCor):
    pass


class SingleLine(BaseCor):
    pass

class Digit(BaseCor):
    pass

class DigitCounter(BaseCor):
    pass

class Duration(BaseCor):
    pass


