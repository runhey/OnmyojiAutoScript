from module.base.decorator import cached_property
from module.ocr.ppocr import TextSystem


class OcrModel:
    @cached_property
    def ch(self):
        return TextSystem()


OCR_MODEL = OcrModel()



if __name__ == "__main__":
    model = OCR_MODEL.ch
    import cv2
    import time
    image = cv2.imread(r"D:\ocr_test_5.png")

    for i in range(10):
        start_time = time.time()
        result = model.detect_and_ocr(image)
        print(result)
        end_time = time.time()
        print(f'耗时：{end_time-start_time}')

