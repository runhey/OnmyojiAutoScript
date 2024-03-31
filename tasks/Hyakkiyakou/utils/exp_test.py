# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2

from datetime import datetime
from pathlib import Path
from cached_property import cached_property

from module.logger import logger
from module.base.timer import Timer

from tasks.Exploration.assets import ExplorationAssets
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_town
from tasks.base_task import BaseTask
from tasks.Script.config_device import ScreenshotMethod, ControlMethod
from tasks.Component.RightActivity.right_activity import RightActivity
from tasks.Restart.assets import RestartAssets

from utils import usage_time
from fast_device import FastDevice


class Step:
    def __init__(self,
                 step_name: str,
                 pos: tuple,
                 time: float,
                 check=None,
                 save_img: bool = False,
                 save_interval: float = 0.1,
                 save_time: float = None,
                 save_max: int = None,
                 save_roi: tuple = (0, 0),
                 info: dict = None,
                 ) -> None:
        self.step_name = step_name
        self.pos = pos
        self.time = time
        self.check = check
        self.save_img = save_img
        self.save_interval = save_interval
        self.save_time = save_time if save_time else time
        self.save_max = save_max
        self.save_roi = save_roi
        self.info = info
        x_start, y_start = self.save_roi
        if x_start > 640 or y_start > 80:
            raise ValueError(f'Invalid roi: {self.save_roi}')

    def __str__(self):
        return f'{self.step_name}'

    def __repr__(self):
        return f'{self.step_name}'


# -----------------------------------------------------------------------



# -----------------------------------------------------------------------

class ExpTest(RightActivity, FastDevice, RestartAssets, ExplorationAssets):

    @cached_property
    def save_path(self) -> Path:
        save_path = Path(f'./tasks/Hyakkiyakou/temp/{self.name}')
        save_path.mkdir(parents=True, exist_ok=True)
        return save_path

    def init(self, name: str):
        self.name = name
        self.config.model.script.device.screenshot_method = ScreenshotMethod.WINDOW_BACKGROUND
        self.config.model.script.device.control_method = ControlMethod.WINDOW_MESSAGE

    def _exit(self):
        self.ui_get_current_page()
        self.ui_goto(page_town)
        self.right_close()
        self.ui_click(self.I_LOGIN_SCROOLL_OPEN, self.I_LOGIN_SCROOLL_CLOSE, interval=1)

    def _go(self):
        pass

    def run_step(self, step: Step):
        logger.hr(f'Running step: {step}', 1)
        cache_image: dict = {}
        timer_step = Timer(step.time)
        timer_save_img = Timer(step.save_time)
        timer_save_interval = Timer(step.save_interval)
        save_image_count = 0
        start_flag = False
        while 1:
            with usage_time('screenshot'):
                self.fast_screenshot()

            if not start_flag:
                with usage_time('click'):
                    self.device.click(x=step.pos[0], y=step.pos[1])
                timer_step.start()
                timer_save_img.start()
                timer_save_interval.start()
                start_flag = True
            if not start_flag:
                continue
            if timer_step.reached():
                break
            if not step.save_img:
                continue
            if timer_save_img.reached():
                continue
            if step.save_max and save_image_count >= step.save_max:
                continue
            if timer_save_interval.reached():
                timer_save_interval.reset()
                save_image_count += 1
                save_name = f't@{self.name}@{int(datetime.now().timestamp() * 1000)}_{save_image_count:03d}.png'
                x_start, y_start = step.save_roi
                img = self.device.image[y_start:y_start + 640, x_start:x_start + 640]
                cache_image[save_name] = img
                logger.info(f'Save image: {save_name}')
                # cv2.imwrite(str(self.save_path / save_name), img)
        if cache_image:
            logger.info(f'Save image: {cache_image.keys()}')
            for key, value in cache_image.items():
                cv2.imwrite(str(self.save_path / key), value)

    def run_town(self):
        step_a = (641, 474)
        step_b = (1165, 481)
        step_c = (641, 556)
        step_d = (1231, 567)
        step_save_roi = (640, 80)
        step_1 = Step('step_1', pos=step_b, time=2)
        step_2 = Step('step_2', pos=step_a, time=2, save_img=True, save_roi=step_save_roi)
        step_3 = Step('step_3', pos=step_b, time=2)
        step_4 = Step('step_4', pos=step_c, time=2, save_img=True, save_roi=step_save_roi)
        step_5 = Step('step_5', pos=step_d, time=2)
        step_6 = Step('step_6', pos=step_a, time=2, save_img=True, save_roi=step_save_roi)
        step_7 = Step('step_7', pos=step_d, time=2)
        step_8 = Step('step_8', pos=step_c, time=2, save_img=True, save_roi=step_save_roi)
        self.run_step(step_1)
        self.run_step(step_2)
        self.run_step(step_3)
        self.run_step(step_4)
        self.run_step(step_5)
        self.run_step(step_6)
        self.run_step(step_7)
        self.run_step(step_8)
