# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2
from time import time, sleep
from random import randint
from cached_property import cached_property

from module.daemon.benchmark import Benchmark
from module.atom.swipe import RuleSwipe
from module.atom.image import RuleImage
from module.logger import logger

from tasks.Script.config_device import ScreenshotMethod, ControlMethod
from tasks.Hyakkiyakou.assets import HyakkiyakouAssets


class ScriptTask(Benchmark, HyakkiyakouAssets):
    Left_Swipe = RuleSwipe(roi_front=(122, 155, 480, 426),
                           roi_back=(667, 147, 461, 427),
                           mode="default",
                           name="Left Swipe")

    def run_simple(self, hero_name: str='test'):
        self.add_one_video(hero_name, index=0)

    def run(self, hero_name: str = 'test'):
        """
        :param hero_name: 你式神的名字
        :return:
        """
        self.screenshot_benchmark()
        self.record_one(self.I_TPAGE_1, self.I_TCHECK_1, hero_name, index=1)
        self.record_one(self.I_TPAGE_2, self.I_TCHECK_2, hero_name, index=2)
        self.record_one(self.I_TPAGE_3, self.I_TCHECK_3, hero_name, index=3)
        self.record_one(self.I_TPAGE_4, self.I_TCHECK_4, hero_name, index=4)
        self.record_one(self.I_TPAGE_5, self.I_TCHECK_5, hero_name, index=5)
        self.record_one(self.I_TPAGE_6, self.I_TCHECK_6, hero_name, index=6)

    def screenshot_benchmark(self):
        self.config.model.script.device.screenshot_method = ScreenshotMethod.WINDOW_BACKGROUND
        # self.config.model.script.device.control_method = ControlMethod.WINDOW_MESSAGE
        self.benchmark([ScreenshotMethod.WINDOW_BACKGROUND])

    @classmethod
    def video(cls, name: str = 'test'):
        return cv2.VideoWriter(f'./log/tmp/{name}_{int(time() * 1000)}.avi',
                               cv2.VideoWriter_fourcc(*'XVID'),
                               10,  # fps
                               (1280, 720),  # frame size
                               )

    def add_one_frame(self, video):
        self.screenshot()
        video.write(self.device.image)
        # 竖直方向在240-480之间随机滑动
        self.device.swipe(p1=(640, 240 + randint(0, 240)), p2=(640 - 64, 240 + randint(0, 240)),
                          distance_check=False)
        # self.device.swipe(p1=(640, 360), p2=(640-64, 360))
        sleep(0.5)

    def add_one_video(self, name: str, index: int = 0):
        video = ScriptTask.video(name=f'{name}_{index}')
        for _ in range(20):
            self.add_one_frame(video)
        video.release()
        cv2.destroyAllWindows()

    def record_one(self, tpage: RuleImage, tcheck: RuleImage, name: str, index: int = 0):
        logger.info(f'开始录制第{index}个视频')
        while 1:
            self.screenshot()
            if self.appear(tpage):
                self.ui_click(tpage, tcheck)
                break
            self.appear_then_click(self.I_SWITCH_BACKGROUND, interval=4)
            sleep(1)
            self.swipe(self.S_TSWIPE, interval=2.5)
        while 1:
            self.screenshot()
            if not self.appear(tpage):
                break
            if self.appear_then_click(tcheck, interval=1.2):
                continue

        logger.info(f'已进入第{index}个背景')
        self.add_one_video(name, index=index)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('test')
    d = Device(c)
    t = ScriptTask(c, d)
    HERO_NAME = 'test'
    # t.run(HERO_NAME)
    t.run_simple(HERO_NAME)
