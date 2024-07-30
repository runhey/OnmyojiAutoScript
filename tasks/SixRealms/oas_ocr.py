import functools

import cv2
import numpy as np


from module.base.utils import color_similarity_2d, load_image
# from module.ocr.ocr import Ocr
from module.ocr.base_ocr import BaseCor




def apply_mask(image, mask):
    image16 = image.astype(np.uint16)
    mask16 = mask.astype(np.uint16)
    mask16 = cv2.merge([mask16, mask16, mask16])
    image16 = cv2.multiply(image16, mask16)
    # cv2.multiply(image16, mask16, dst=image16)
    image16 = cv2.convertScaleAbs(image16, alpha=1 / 255)
    # cv2.convertScaleAbs(image16, alpha=1 / 255, dst=image16)
    # Image.fromarray(image16.astype(np.uint8)).show()
    return image16.astype(np.uint8)


class VerticalText(BaseCor):
    @staticmethod
    def rotate_image(image):
        height, width = image.shape[0:2]
        if height * 1.0 / width >= 1.5:
            image = np.rot90(image)
            return image
        return image

    def detect_and_ocr(self, *args, **kwargs):
        # Try hard to lower TextSystem.box_thresh
        backup = self.model.text_detector.box_thresh
        # Patch text_recognizer
        text_recognizer = self.model.text_recognizer
        # Lower drop_score
        lower_score = functools.partial(self.model.detect_and_ocr, drop_score=0.1)
        detect_and_ocr = self.model.detect_and_ocr

        def vertical_text_recognizer(img_crop_list):
            img_crop_list = [VerticalText.rotate_image(i) for i in img_crop_list]
            result = text_recognizer(img_crop_list)
            return result

        self.model.text_detector.box_thresh = 0.2
        self.model.text_recognizer = vertical_text_recognizer
        self.model.detect_and_ocr = lower_score

        try:
            result = super().detect_and_ocr(*args, **kwargs)
        finally:
            self.model.text_detector.box_thresh = backup
            self.model.text_recognizer = text_recognizer
            self.model.detect_and_ocr = detect_and_ocr
        return result


class StoneOcr(VerticalText):
    def pre_process(self, image):
        yuv = cv2.cvtColor(image, cv2.COLOR_RGB2YUV)
        _, u, _ = cv2.split(yuv)
        cv2.subtract(128, u, dst=u)
        cv2.multiply(u, 8, dst=u)

        color = color_similarity_2d(image, color=(234, 213, 181))
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        _, _, v = cv2.split(hsv)
        image = apply_mask(image, u)
        image = apply_mask(image, color)
        image = apply_mask(image, v)

        cv2.convertScaleAbs(image, alpha=3, dst=image)
        cv2.subtract((255, 255, 255, 0), image, dst=image)

        # from PIL import Image
        # Image.fromarray(image.astype(np.uint8)).show()
        return image


if __name__ == '__main__':
    from tasks.SixRealms.assets import SixRealmsAssets
    file = r'C:\Users\Ryland\Desktop\Desktop\20.png'
    image = load_image(file)
    ocr = StoneOcr(roi=(0,0,1280,720), area=(0,0,1280,720), mode="Full", method="Default", keyword="", name="ocr_map")
    results = ocr.detect_and_ocr(image)
    for r in results:
        print(r.box, r.ocr_text)
