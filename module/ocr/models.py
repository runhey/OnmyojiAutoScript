from typing import List

import cv2
import time

import numpy as np

import sys
import time
from module.base.decorator import cached_property
from module.ocr.onnx_paddle_ocr import ONNXPaddleOcr


class OcrModel:
    @cached_property
    def ch(self):
        return ONNXPaddleOcr(use_angle_cls=True,use_gpu=False)


OCR_MODEL = OcrModel()



if __name__ == "__main__":
    model = OCR_MODEL.ch
    import cv2
    import time
    from memory_profiler import profile
    image = cv2.imread(r"d:\2025-07-17_12-52-22-184354.png")

    # 引入ocr 会导致非常巨大的内存开销
    @profile
    def test_memory():
        for i in range(2):
            start_time = time.time()
            result = model.ocr(image)
            print(result)
            end_time = time.time()
            print(f'耗时：{end_time-start_time}')

    test_memory()
