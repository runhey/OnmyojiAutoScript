# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import cv2
import numpy as np

from datetime import datetime, timedelta
from numpy import uint8, fromfile
from random import choice
from cached_property import cached_property
# Use cmd to install: ./toolkit/python.exe -m pip install -i https://pypi.org/simple/ oashya --trusted-host pypi.org
# update oashya:  ./toolkit/python.exe -m pip install --upgrade oashya
from oashya.tracker import Tracker
from oashya.labels import label2id
from oashya.utils import draw_tracks

from module.exception import TaskEnd
from module.logger import logger
from module.exception import RequestHumanTakeover
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_hyakkiyakou
from tasks.Hyakkiyakou.config import Hyakkiyakou as HyakkiyakouConfig
from tasks.Hyakkiyakou.config import InferenceEngine, ModelPrecision
from tasks.Hyakkiyakou.assets import HyakkiyakouAssets
from tasks.Hyakkiyakou.agent.agent import Agent
from tasks.Hyakkiyakou.slave.hya_slave import HyaSlave
from tasks.Hyakkiyakou.debugger import Debugger


def plot_save(image, boxes):
    color_palette = np.random.uniform(0, 255, size=(226, 3))
    for box in boxes:
        _cls = box[0]
        _scores = box[1]
        _x, _y, _w, _h = box[2]
        x1 = int(_x - _w / 2)
        y1 = int(_y - _h / 2)
        x2 = int(_x + _w / 2)
        y2 = int(_y + _h / 2)
        cv2.rectangle(image, (x1, y1), (x2, y2), color_palette[_cls], 2)
        #
        cv2.putText(image, f'{_cls} {_scores:.2f}', (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_palette[_cls],
                    2)
    save_file = './tasks/Hyakkiyakou/temp/image.png'
    cv2.imwrite(save_file, image)


class ScriptTask(GameUi, HyaSlave):

    @property
    def _config(self):
        return self.config.hyakkiyakou

    @cached_property
    def tracker(self) -> Tracker:
        hyakkiyakou_models = self._config.hyakkiyakou_models
        conf = hyakkiyakou_models.conf_threshold
        nms = hyakkiyakou_models.iou_threshold
        if conf < 0.2 or conf > 1:
            raise RequestHumanTakeover('conf_threshold should be in [0.2, 1]')
        if nms < 0.2 or nms > 1:
            raise RequestHumanTakeover('iou_threshold should be in [0.2, 1]')
        inf_en = 'onnxruntime' if hyakkiyakou_models.inference_engine == InferenceEngine.ONNXRUNTIME else 'tensorrt'
        precision = 'fp32' if hyakkiyakou_models.model_precision == ModelPrecision.FP32 else 'int8'
        # 这个坑后面在补
        if inf_en == 'tensorrt' or precision == 'int8':
            raise RequestHumanTakeover('Only support onnxruntime')
        debug_info: bool = self._config.debug_config.hya_info
        args = {
            'conf_threshold': conf,
            'iou_threshold': nms,
            'precision': precision,
            'inference_engine': inf_en,
            'debug': debug_info,
        }
        return Tracker(args=args)

    @cached_property
    def agent(self) -> Agent:
        hya_config = self._config.hyakkiyakou_config
        sp = hya_config.hya_sp
        ssr = hya_config.hya_ssr
        sr = hya_config.hya_sr
        r = hya_config.hya_r
        n = hya_config.hya_n
        g = hya_config.hya_g
        weights: list = [sp, ssr, sr, r, n, g]
        str_priorities: str = hya_config.hya_priorities
        if str_priorities == '':
            priorities = []
        else:
            str_priorities = str_priorities.replace(' ', '').replace('，', ',')
            try:
                priorities = [label2id(s) for s in str_priorities.split(',')]
            except Exception as e:
                logger.error(f'Priority error: {str_priorities}')
                logger.error(e)
                raise RequestHumanTakeover
        strategy: dict = {
            'weights': weights,
            'priorities': priorities,
            'invite_friend': hya_config.hya_invite_friend,
            'auto_bean': hya_config.hya_auto_bean
        }
        return Agent(strategy=strategy)

    @cached_property
    def debugger(self) -> Debugger:
        debug_config = self._config.debug_config
        hya_interval = debug_config.hya_interval
        hya_save_result = debug_config.hya_save_result
        if hya_interval <= 100 or hya_interval >= 1000:
            raise RequestHumanTakeover('screenshot_interval must be between 1000 and 10000')
        self.set_fast_screenshot_interval(hya_interval)
        return Debugger(info_enable=debug_config.hya_info, 
                        continuous_learning=debug_config.continuous_learning,
                        hya_save_result=hya_save_result)

    def run(self):
        hya_count: int = 0
        self.limit_count: int = self._config.hyakkiyakou_config.hya_limit_count
        limit_time = self._config.hyakkiyakou_config.hya_limit_time
        self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute,
                                               seconds=limit_time.second)
        self.ui_get_current_page()
        self.ui_goto(page_hyakkiyakou)


        while 1:
            if hya_count >= self.limit_count:
                logger.info('Hyakkiyakou count limit out')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('Hyakkiyakou time limit out')
                break

            self.one()
            hya_count += 1

        while 1:
            self.screenshot()

            if not self.appear(self.I_HACCESS):
                continue
            if self.appear(self.I_HCLOSE_RED):
                break
        self.ui_click_until_disappear(self.I_HCLOSE_RED)
        self.set_next_run(task='Hyakkiyakou', success=True, finish=False)
        raise TaskEnd

    def one(self):
        self.reset_state()
        if not self.appear(self.I_HACCESS):
            logger.warning('Page Error')
        if self._config.hyakkiyakou_config.hya_invite_friend:
            self.invite_friend()
        # start
        self.ui_click(self.I_HACCESS, self.I_HSTART, interval=2)
        self.wait_until_appear(self.I_HTITLE)
        # 随机选一个
        click_button = choice([self.C_HSELECT_1, self.C_HSELECT_2, self.C_HSELECT_3])
        while 1:
            self.screenshot()
            if not self.appear(self.I_HTITLE):
                break
            if self.appear_then_click(self.I_HSTART, interval=2):
                continue
            if not self.appear(self.I_HSELECTED):
                self.click(click_button, interval=2)
        self.device.stuck_record_add('BATTLE_STATUS_S')
        # 正式开始
        logger.hr('Start Hyakkiyakou')
        init_bean_flag: bool = False
        last_action = [0, 0, False, 10]
        self.hya_fs_check_timer.reset()
        if self._config.debug_config.hya_show:
            self.debugger.show_start()
        while 1:
            self.fast_screenshot(screenshot=self._config.debug_config.hya_screenshot_method)
            if self.appear(self.I_HEND):
                break
            if not self.appear(self.I_CHECK_RUN):
                continue
            if not init_bean_flag:
                init_bean_flag = True
                self.bean_05to10()
                time.sleep(0.5)
            if not self.appear(self.I_HFREEZE):
                # --------------------------------------------------------
                self.slave_state = self.update_state()
                tracks = self.tracker(image=self.device.image, response=last_action)
                last_action = self.agent.decision(tracks=tracks, state=self.slave_state)
                self.do_action(last_action, state=self.slave_state)
            else:
                # TODO freeze state
                tracks = []
            # debug
            if self._config.debug_config.hya_show:
                draw_image = draw_tracks(self.device.image, tracks=tracks)
                self.debugger.show_sync(image=draw_image)
            if self._config.debug_config.continuous_learning:
                self.debugger.deal_learning(image=self.device.image, tracks=tracks)
            if self._config.debug_config.hya_info:
                self.debugger.show_info(tracker=self.tracker, f=self.agent.focus)

        logger.info('Hyakkiyakou End')
        if self._config.debug_config.hya_show:
            self.debugger.show_stop()
        if self._config.debug_config.hya_save_result:
            # 走个动画
            time.sleep(1.5)
            self.debugger.save_result(self.device.image)
        self.ui_click(self.I_HEND, self.I_HACCESS)
        self.debugger.save_images()
        del self.debugger
        # you maybe update oashya
        self.tracker.clear_tracks()

    def do_action(self, action: list, state):
        x, y, throw, bean = action
        if not throw:
            return
        if state[0] <= 0:
            return
        self.fast_click(x=x, y=y, control_method=self._config.debug_config.hya_control_method)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)

    t = ScriptTask(c, d)
    t.run()

    # from tasks.Hyakkiyakou.agent.tagent import test_observe, test_state
    # test_state()
    # from debugger import test_track
    # test_track(show=False)
    pass

