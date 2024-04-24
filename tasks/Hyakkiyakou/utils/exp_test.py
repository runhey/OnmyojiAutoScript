# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2
import random

from datetime import datetime
from pathlib import Path
from cached_property import cached_property

from module.logger import logger
from module.base.timer import Timer
from module.atom.click import RuleClick

from tasks.Exploration.assets import ExplorationAssets
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_town, page_exploration
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
        self.ui_get_current_page()
        self.ui_goto(page_exploration)

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

    def exp_enter(self, layer: int = 25):
        w = 188
        h = 80
        x_25, y_25 = 1052, 208
        x_26, y_26 = 1052, 316
        x_27, y_27 = 1052, 443
        x_28, y_28 = 1052, 564
        exp_click_25 = RuleClick(roi_front=(x_25, y_25, w, h), roi_back=(x_25, y_25, w, h), name="exp_click_25")
        exp_click_26 = RuleClick(roi_front=(x_26, y_26, w, h), roi_back=(x_26, y_26, w, h), name="exp_click_26")
        exp_click_27 = RuleClick(roi_front=(x_27, y_27, w, h), roi_back=(x_27, y_27, w, h), name="exp_click_27")
        exp_click_28 = RuleClick(roi_front=(x_28, y_28, w, h), roi_back=(x_28, y_28, w, h), name="exp_click_28")
        match layer:
            case 25:
                exp_click = exp_click_25
            case 26:
                exp_click = exp_click_26
            case 27:
                exp_click = exp_click_27
            case 28:
                exp_click = exp_click_28
            case _:
                exp_click = exp_click_28
        self.ui_click(exp_click, self.I_E_EXPLORATION_CLICK)
        while 1:
            self.screenshot()
            if self.appear(self.I_E_AUTO_ROTATE_ON) or self.appear(self.I_E_AUTO_ROTATE_OFF):
                break
            if self.appear_then_click(self.I_E_EXPLORATION_CLICK, interval=1):
                continue
        from time import sleep
        sleep(1)
        logger.info(f'Enter exploration {layer}')

    def exp_exit(self):
        while 1:
            self.screenshot()
            if self.appear(self.I_UI_BACK_RED):
                break
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                continue
            if self.appear_then_click(self.I_E_EXIT_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_UI_BACK_BLUE, interval=1.5):
                continue
        self.ui_click_until_disappear(self.I_UI_BACK_RED, interval=0.5)

    def run_exp_25(self):
        pos_right = 1270
        pos_left = 260
        pos_top = 390
        pos_bottom = 500
        pos_level = (pos_top + pos_bottom) / 2

        step_1 = Step('step_1', pos=(pos_right, random.randint(pos_top, pos_bottom)), time=2.1)
        step_2 = Step('step_2', pos=(pos_right, random.randint(pos_top, pos_bottom)), time=2.1)
        step_3 = Step('step_3', pos=(pos_right, random.randint(pos_top, pos_bottom)), time=2.1)
        step_4 = Step('step_4', pos=(pos_right, random.randint(pos_top, pos_bottom)), time=2.1)
        step_5 = Step('step_5', pos=(pos_right, pos_bottom), time=2.1)

        save_time = 1.6
        back_1 = Step('back_1', pos=(pos_left, pos_bottom), time=1, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_2 = Step('back_2', pos=(pos_left, pos_top), time=2, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_3 = Step('back_3', pos=(pos_left, pos_top), time=2, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_4 = Step('back_4', pos=(pos_left, pos_bottom), time=2,  save_time=1.6, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_5 = Step('back_5', pos=(pos_left, pos_level), time=save_time, save_img=True,
                      save_roi=(random.randint(100, 540), 80))

        self.run_step(step_1)
        self.run_step(step_2)
        self.run_step(step_3)
        self.run_step(step_4)
        self.run_step(step_5)
        self.run_step(back_1)
        self.run_step(back_2)
        self.run_step(back_3)
        self.run_step(back_4)
        self.run_step(back_5)

    def run_exp_26(self):
        pos_right = 1270
        pos_left = 260
        pos_top = 454
        pos_bottom = 620
        pos_level = (pos_top + pos_bottom) / 2
        step_1 = Step('step_1', pos=(pos_right, random.randint(pos_top, pos_bottom)), time=2.1)
        step_2 = Step('step_2', pos=(pos_right, random.randint(pos_top, pos_bottom)), time=2.1)
        step_3 = Step('step_3', pos=(pos_right, random.randint(pos_top, pos_bottom)), time=2.1)
        step_4 = Step('step_4', pos=(pos_right, pos_bottom), time=2.1)
        self.run_step(step_1)
        self.run_step(step_2)
        self.run_step(step_3)
        self.run_step(step_4)

        back_1 = Step('back_1', pos=(pos_left, pos_bottom), time=1, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_2 = Step('back_2', pos=(pos_left, pos_top), time=2, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_3 = Step('back_3', pos=(pos_left, pos_top), time=2, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_4 = Step('back_4', pos=(pos_left, pos_bottom), time=2, save_time=1.6, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_5 = Step('back_5', pos=(pos_left, pos_level), time=1.7, save_img=True,
                      save_roi=(random.randint(100, 540), 80))

        self.run_step(back_1)
        self.run_step(back_2)
        self.run_step(back_3)
        self.run_step(back_4)
        self.run_step(back_5)

    def run_exp_27(self):
        pos_right = 1270
        pos_left = 260
        pos_top = 550
        pos_bottom = 620
        pos_level = (pos_top + pos_bottom) / 2
        step_1 = Step('step_1', pos=(pos_right, random.randint(pos_top, pos_bottom)), time=2.1)
        step_2 = Step('step_2', pos=(pos_right, random.randint(pos_top, pos_bottom)), time=2.3)
        step_3 = Step('step_3', pos=(pos_right, random.randint(pos_top, pos_bottom)), time=2.5)
        step_4 = Step('step_4', pos=(pos_right, pos_bottom), time=2.9)
        self.run_step(step_1)
        self.run_step(step_2)
        self.run_step(step_3)
        self.run_step(step_4)

        back_1 = Step('back_1', pos=(pos_left, pos_bottom), time=1, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_2 = Step('back_2', pos=(pos_left, pos_top), time=2, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_3 = Step('back_3', pos=(pos_left, pos_top), time=2, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_4 = Step('back_4', pos=(pos_left, pos_bottom), time=2, save_time=1.6, save_img=True,
                      save_roi=(random.randint(100, 540), 80))
        back_5 = Step('back_5', pos=(pos_left, pos_level), time=1.4, save_img=True,
                      save_roi=(random.randint(100, 540), 80))

        self.run_step(back_1)
        self.run_step(back_2)
        self.run_step(back_3)
        self.run_step(back_4)
        self.run_step(back_5)

    def run_main(self):
        from time import sleep
        self.ui_get_current_page()
        self.ui_goto(page_main)
        sleep(1)

        pos_right = 1270
        pos_left = 540
        pos_top = 540
        pos_bottom = 660
        step_1 = Step('step_1', pos=(pos_right, pos_top), time=2.1)
        back_1 = Step('back_1', pos=(pos_left, pos_top), time=1.7, save_img=True, save_roi=(640, 80))
        step_2 = step_1
        step_2.name = 'step_2'
        back_2 = Step('back_2', pos=(pos_left, pos_bottom), time=1.7, save_img=True, save_roi=(640, 80))

        self.run_step(step_1)
        self.run_step(back_1)
        self.run_step(step_2)
        self.run_step(back_2)

    def back_main(self):
        self.ui_get_current_page()
        self.ui_goto(page_main)
