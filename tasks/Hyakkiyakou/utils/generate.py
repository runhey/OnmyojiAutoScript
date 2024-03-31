# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2
from time import time, sleep
from random import randint
from pathlib import Path
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
    hero_name = ''

    def run_simple(self, hero_name: str='test'):
        self.screenshot_benchmark()
        ScriptTask.hero_name = hero_name
        self.add_one_video(hero_name, index=0)

    def run(self, hero_name: str = 'test'):
        """
        :param hero_name: 你式神的名字
        :return:
        """
        ScriptTask.hero_name = hero_name
        self.screenshot_benchmark()
        self.record_one(self.I_TPAGE_1, self.I_TCHECK_1, hero_name, index=1)
        self.record_one(self.I_TPAGE_2, self.I_TCHECK_2, hero_name, index=2)
        self.record_one(self.I_TPAGE_3, self.I_TCHECK_3, hero_name, index=3)
        self.record_one(self.I_TPAGE_4, self.I_TCHECK_4, hero_name, index=4)
        self.record_one(self.I_TPAGE_6, self.I_TCHECK_6, hero_name, index=6)
        self.record_one(self.I_TPAGE_5, self.I_TCHECK_5, hero_name, index=5)

        self.back_one()

    def screenshot_benchmark(self):
        self.config.model.script.device.screenshot_method = ScreenshotMethod.WINDOW_BACKGROUND
        # self.config.model.script.device.control_method = ControlMethod.WINDOW_MESSAGE
        self.benchmark([ScreenshotMethod.WINDOW_BACKGROUND])

    @classmethod
    def video(cls, name: str = 'test'):
        path = f'./log/tmp/{ScriptTask.hero_name}'
        Path(path).mkdir(parents=True, exist_ok=True)
        return cv2.VideoWriter(f'{path}/{name}@{int(time() * 1000)}.avi',
                               cv2.VideoWriter_fourcc(*'XVID'),
                               10,  # fps
                               (1280, 720),  # frame size
                               )

    def add_one_frame(self, video):
        self.screenshot()
        video.write(self.device.image)
        # 竖直方向在240-480之间随机滑动
        self.device.swipe(p1=(640, 690 + randint(0, 28)), p2=(640 - 64, 690 + randint(0, 28)),
                          distance_check=False)
        # self.device.swipe(p1=(640, 360), p2=(640-64, 360))
        sleep(0.05)

    def add_one_video(self, name: str, index: int = 0):
        video = ScriptTask.video(name=f'{name}@{index}')
        for _ in range(20):
            self.add_one_frame(video)
        video.release()
        cv2.destroyAllWindows()

    def record_one(self, tpage: RuleImage, tcheck: RuleImage, name: str, index: int = 0):
        logger.hr(f'开始录制第{index}个视频')
        skip_swipe_time = 2
        while 1:
            self.screenshot()
            self.appear_then_click(self.I_SWITCH_BACKGROUND, interval=4)
            sleep(0.5)
            if self.appear(tpage) or self.appear(tcheck):
                # self.ui_click(tpage, tcheck)
                click_count = 0
                while 1:
                    self.screenshot()
                    if self.appear(tcheck):
                        break
                    if tcheck == self.I_TCHECK_2 and self.appear(self.I_TCHECK_22):
                        logger.warning('I_TCHECK_22')
                        break
                    if tcheck == self.I_TCHECK_3 and self.appear(self.I_TCHECK_32):
                        logger.warning('I_TCHECK_32')
                        break
                    if click_count > 5:
                        logger.warning('已经点击背景五次了')
                        break

                    if self.appear_then_click(tpage, interval=2):
                        click_count += 1
                        continue
                break

            sleep(0.5)
            if skip_swipe_time > 0:
                skip_swipe_time -= 1
                continue
            self.swipe(self.S_TSWIPE, interval=1.5)
            sleep(1)
        while 1:
            self.screenshot()
            if not self.appear(tpage):
                break
            if self.appear_then_click(tcheck, interval=1.2):
                continue
            if self.click(self.C_CLICK, interval=4):
                continue
            if self.appear_then_click(self.I_TCHECK_22, interval=2):
                continue
            if self.appear_then_click(self.I_TCHECK_32, interval=2):
                continue

        logger.info(f'已进入第{index}个背景')
        sleep(0.5)
        self.add_one_video(name, index=index)

    def back_one(self):
        while 1:
            self.screenshot()
            if (self.appear(self.I_TPAGE_5)
                    or self.appear(self.I_TPAGE_6)
                    or self.appear(self.I_TCHECK_4)):
                break
            if self.appear_then_click(self.I_SWITCH_BACKGROUND, interval=1.2):
                continue
        while 1:
            self.screenshot()
            if self.appear(self.I_TPAGE_1):
                break
            if self.swipe(self.S_TBACK, interval=2):
                sleep(1.5)
                continue
        self.ui_click(self.I_TPAGE_1, self.I_TCHECK_1)
        while 1:
            self.screenshot()
            if not self.appear(self.I_TPAGE_1):
                break
            if self.appear_then_click(self.I_TCHECK_1, interval=1.2):
                continue






if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas2')
    d = Device(c)
    t = ScriptTask(c, d)
    HERO_NAME = 'g_015'
    # t.run_simple(HERO_NAME)
    t.run(HERO_NAME)






