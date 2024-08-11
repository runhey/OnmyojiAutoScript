# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2
from cached_property import cached_property

from tasks.base_task import BaseTask


class HyaColor(BaseTask):
    BUFF_STATE_POS0: tuple[int] = (190, 42, 57, 37, 46)
    BUFF_STATE_POS1: tuple[int] = (370, 35, 58, 39, 53)
    BUFF_STATE_POS2: tuple[int] = (905, 35, 46, 29, 37)
    BUFF_STATE_POS3: tuple[int] = (1060, 33, 53, 33, 39)

    BEAN_NUM10: tuple[int] = (550, 657, 44, 32, 43)
    BEAN_NUM05: tuple[int] = (400, 657, 44, 32, 43)

    @cached_property
    def buff_colors(self) -> list[tuple[int]]:
        return [self.BUFF_STATE_POS0,
                self.BUFF_STATE_POS1,
                self.BUFF_STATE_POS2,
                self.BUFF_STATE_POS3]

    def show_point_color(self, x: int, y: int):
        color = self.device.image[y, x]
        print(f"({x}, {y}) color: {color}")
        return color

    def match_color(self, package: tuple, offset: int=5) -> bool:
        x, y, r, g, b = package
        img_r, img_g, img_b = self.device.image[y, x]
        if abs(img_r - r) > offset:
            return False
        if abs(img_g - g) > offset:
            return False
        if abs(img_b - b) > offset:
            return False
        return True



if __name__ == "__main__":
    import timeit
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    hd = HyaColor(c, d)
    img = cv2.imread(r'E:\Project\OnmyojiAutoScript\tasks\Hyakkiyakou\temp\20240615T144058\all1718433698934.png')
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    hd.device.image = img

    # print(hd.show_point_color(400, 657))
    # print(hd.match_color(hd.BUFF_STATE_POS1))

