# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2
import time
from datetime import timedelta, datetime
from cached_property import cached_property
from random import choice
from pathlib import Path


from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.Script.config_device import ScreenshotMethod, ControlMethod
from tasks.base_task import BaseTask
from tasks.Exploration.version import highlight

class GetAnimation(BaseTask):

    @cached_property
    def save_folder(self) -> Path:
        save_time = datetime.now().strftime('%Y%m%dT%H%M%S')
        save_folder = Path(f'./log/temp/{save_time}')
        save_folder.mkdir(parents=True, exist_ok=True)
        return save_folder

    def run_screenshot(self):
        self.config.model.script.device.screenshot_method = ScreenshotMethod.WINDOW_BACKGROUND
        run_timer = Timer(3)
        sho_timer = Timer(0.1)
        run_timer.start()
        sho_timer.start()
        save_images = {}
        while 1:
            if run_timer.reached():
                break
            if sho_timer.reached():
                sho_timer.reset()
                image = self.device.screenshot_window_background()
                # image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                image = highlight(image)
                time_now1 = int(time.time() * 1000)
                save_images[time_now1] = image
        for time_now, image in save_images.items():
            cv2.imwrite(str(self.save_folder / f'all{time_now}.png'), image)
