# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

import cv2
from module.ocr.ppocr import TextSystem
# from ppocronnx.predict_system import TextSystem




if __name__ == "__main__":

    text_sys = TextSystem()

    # 检测并识别文本
    img = cv2.imread('D:/33357.jpg')
    if img is None:
        print("Error: img is None")
        exit(1)


    res = text_sys.detect_and_ocr(img)
    if res is None:
        print("Error: res is None")
        exit(1)
    for boxed_result in res:
        print("{}, {:.3f}".format(boxed_result.ocr_text, boxed_result.score))
        print(boxed_result.box)

    # res = text_sys.ocr_single_line(img)
    # print(res)
