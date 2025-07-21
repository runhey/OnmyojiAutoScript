from typing import List

import cv2
import numpy as np
import onnxocr.onnx_paddleocr as onnxocr

class BoxedResult(object):
    box: List[int]
    text_img: np.ndarray
    ocr_text: str
    score: float

    def __init__(self, box, text_img, ocr_text, score):
        self.box = box
        self.text_img = text_img
        self.ocr_text = ocr_text
        self.score = score

    def __str__(self):
        return 'BoxedResult[%s, %s]' % (self.ocr_text, self.score)

    def __repr__(self):
        return self.__str__()

class ONNXPaddleOcr(onnxocr.ONNXPaddleOcr):
    def __init__(self,
                 use_gpu=True,
                 gpu_mem=500,
                 gpu_id=0,
                 use_tensorrt=False,
                 precision="fp32",
                 drop_score=0.5,
                 use_angle_cls=True,
                 cpu_threads=10,
                 benchmark=False,
                 use_onnx=False
                 ):
        super().__init__(
            use_gpu=use_gpu,
            gpu_mem=gpu_mem,
            gpu_id=gpu_id,
            use_tensorrt=use_tensorrt,
            precision=precision,
            drop_score=drop_score,
            use_angle_cls=use_angle_cls,
            cpu_threads=cpu_threads,
            benchmark=benchmark,
            use_onnx=use_onnx
        )

    def detect_and_ocr(self,img: np.ndarray):
        """
        Detect text boxes and recognize text from the image.
        :param img: Input image in RGB format.
        :return: List of BoxedResult containing detected boxes, cropped images, recognized text, and scores.
        """
        rec_res = self.ocr(img, det=True, rec=True, cls=True)
        if not rec_res:
            return []
        rec_res = rec_res[0]
        res = []
        for box, rec_result in rec_res:
            text, score = rec_result
            if score >= self.drop_score:
                res.append(BoxedResult(box, img, text, score))
        return res

    def ocr_lines(self, img_list: List[np.ndarray]):
        tmp_img_list = []
        for img in img_list:
            img_height, img_width = img.shape[0:2]
            if img_height * 1.0 / img_width >= 1.5:
                img = np.rot90(img)
            tmp_img_list.append(img)

        rec_res = self.text_recognizer(tmp_img_list)
        return rec_res
    def ocr_single_line(self, img):
        res = self.ocr_lines([img])
        if res:
            return res[0]
        return None
