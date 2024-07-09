import timeit
import numpy as np

from module.base.timer import Timer
from module.logger import logger
from module.base.utils import point2str
from module.exception import RequestHumanTakeover, GameStuckError
from tasks.base_task import BaseTask


def image_black(img) -> bool:
    for y, x in [(0, 0), (719, 1279), (719, 0), (0, 1279)]:
        if np.all(img[y, x] != 0):
            return False
    return True


class HyaDevice(BaseTask):
    """
    这个类主要是是优化截屏点击速度
    1. 使用特别的method
    2. 扔掉中间的冗余校验
    3. 考虑JIT加速
    我宣布世界上最好的 Linux 系统是 Windows
    """
    hya_screenshot_interval = Timer(0.2)  # 300ms
    hya_fs_check_timer = Timer(5 * 60)  # 五分钟跑不完就应该是出问题了

    def fast_screenshot(self):
        self.hya_screenshot_interval.wait()
        self.hya_screenshot_interval.reset()
        self.device.image = self.device.screenshot_window_background()
        if image_black(self.device.image):
            logger.error('Screenshot image is black, try again')
            raise RequestHumanTakeover('Screenshot image is black, try again')
        if self.hya_fs_check_timer.reached():
            logger.error('Fast screenshot check timer reached')
            logger.error('Five minutes have not ended, the game is probably stuck, please check the game')
            raise GameStuckError
        return self.device.image

    def fast_click(self, x: int, y: int) -> None:
        logger.info(
            'Click %s @ %s' % (point2str(x, y), 'Click')
        )
        self.device.click_window_message(x=x, y=y, fast=True)

    def set_fast_screenshot_interval(self, interval: float):
        """

        @param interval: ms
        @return:
        """
        self.hya_screenshot_interval = Timer(interval / 1000.)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    hd = HyaDevice(c, d)

    # def screenshot():
    #     global hd
    #     # hd.fast_screenshot()
    #     hd.fast_click(420, 370)
    #     hd.fast_click(750, 400)
    # execution_time = timeit.timeit(screenshot, number=50)
    # print(f"执行总的时间: {execution_time * 1000} ms")

    hd.fast_screenshot()

