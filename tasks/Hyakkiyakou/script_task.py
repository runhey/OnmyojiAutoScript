# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2
import numpy as np

from datetime import datetime
from numpy import uint8, fromfile
from cached_property import cached_property
# Use cmd to install: ./toolkit/python.exe -m pip install -i https://pypi.org/simple/ oashya --trusted-host pypi.org
from oashya.tracker import Tracker

from module.exception import TaskEnd
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_hyakkiyakou
from tasks.Hyakkiyakou.config import Hyakkiyakou as HyakkiyakouConfig
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

    @cached_property
    def tracker(self) -> Tracker:
        args = {}
        return Tracker(args=args)

    @cached_property
    def agent(self) -> Agent:
        return Agent()

    @cached_property
    def debugger(self) -> Debugger:
        return Debugger()

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_hyakkiyakou)

        self.one()

        self.ui_click_until_disappear(self.I_UI_BACK_RED)
        self.set_next_run(task='Hyakkiyakou', success=True, finish=False)
        raise TaskEnd

    def one(self):
        pass



if __name__ == '__main__':
    # from module.config.config import Config
    # from module.device.device import Device
    from debugger import test_track

    # c = Config('oas1')
    # d = Device(c)

    # t = ScriptTask(c, d)
    # t.run()
    test_track(show=True)
