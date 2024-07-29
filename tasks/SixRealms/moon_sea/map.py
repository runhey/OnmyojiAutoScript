import cv2
import numpy as np
from numpy import uint8, fromfile

from tasks.base_task import BaseTask
from tasks.SixRealms.assets import SixRealmsAssets
from tasks.SixRealms.common import MoonSeaType


def binaryzate(img):
    img0 = img[..., 0]
    img1 = img[..., 1]
    img2 = img[..., 2]

    mask0 = cv2.inRange(img0, MoonSeaMap.COLOR_RANGE_0[0], MoonSeaMap.COLOR_RANGE_0[1])
    result0 = cv2.bitwise_and(img0, img0, mask=mask0)
    mask1 = cv2.inRange(img1, 200, 250)
    result1 = cv2.bitwise_and(img1, img1, mask=mask1)
    mask2 = cv2.inRange(img2, 180, 230)
    result2 = cv2.bitwise_and(img2, img2, mask=mask2)

    result = np.zeros(img.shape, dtype=np.uint8)
    result[..., 0]= result0
    result[..., 1]= result1
    result[..., 2]= result2
    return  result


class MoonSeaMap(BaseTask, SixRealmsAssets):

    LOWER_COLOR = np.array([220, 190, 170])
    UPPER_COLOR = np.array([260, 250, 230])
    COLOR_RANGE_0 = [220, 250]

    def detect_current(self) -> list[tuple]:
        # self.screenshot()
        img = self.device.image
        # img = 255 - img
        # print(img[403, 384])
        # print(img[444, 378])
        # print(img[411, 381])
        # binary_img = img
        # img = cv2.inRange(img, self.LOWER_COLOR, self.UPPER_COLOR)

        # cv2.imwrite('test_0.png', img[..., 0])
        # cv2.imwrite('test_1.png', img[..., 1])
        # cv2.imwrite('test_2.png', img[..., 2])

        img = binaryzate(img)
        # iii = np.zeros((720, 1280, 3), dtype=np.uint8)
        # iii[..., 0] = img
        # iii[..., 1] = img
        # iii[..., 2] = img
        # img = iii

        cv2.imshow('Binary Image', img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


        boxs = self.O_OCR_MAP.detect_and_ocr(img)
        for box in boxs:
            print(box)
        return []


def _test():
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = MoonSeaMap(c, d)
    import cv2
    file_image = r'C:\Users\Ryland\Desktop\Desktop\34.png'
    image = cv2.imdecode(fromfile(str(file_image), dtype=uint8), -1)
    # image = cv2.imread(file_image)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    t.device.image = image

    t.detect_current()


def _test2():
    file_image = r'test_1.png'
    image = cv2.imdecode(fromfile(str(file_image), dtype=uint8), -1)
    print(image.shape)
    result = image
    mask = cv2.inRange(image, 210, 250)
    # mask = 255 * mask
    result = cv2.bitwise_and(image, image, mask=mask)
    # 显示结果
    cv2.imshow('Result', result)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == '__main__':
    _test()
