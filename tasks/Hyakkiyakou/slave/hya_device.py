import timeit

from module.base.timer import Timer
from module.logger import logger
from module.base.utils import point2str
from tasks.base_task import BaseTask


class HyaDevice(BaseTask):
    """
    这个类主要是是优化截屏点击速度
    1. 使用特别的method
    2. 扔掉中间的冗余校验
    3. 考虑JIT加速
    我宣布世界上最好的 Linux 系统是 Windows
    """
    hya_screenshot_interval = Timer(0.2)  # 300ms

    def fast_screenshot(self):
        self.hya_screenshot_interval.wait()
        self.hya_screenshot_interval.reset()
        self.device.image = self.device.screenshot_window_background()
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

    def screenshot():
        global hd
        # hd.fast_screenshot()
        hd.fast_click(420, 370)
        hd.fast_click(750, 400)
    execution_time = timeit.timeit(screenshot, number=50)
    print(f"执行总的时间: {execution_time * 1000} ms")
