import cv2
import time
import copy
import numpy as np

from datetime import datetime
from pathlib import Path
from numpy import uint8, fromfile
from cached_property import cached_property

from oashya.tracker import Tracker
from oashya.labels import CLASSINDEX as CI
from oashya.labels import id2label, id2name
from module.logger import logger
from tasks.Hyakkiyakou.agent.focus import Focus
from tasks.Hyakkiyakou.debugger import Debugger


def generate_gaussian_patch(size=(300, 300), mean=0, std_dev=60):
    x = np.linspace(-150, 150, size[1])
    y = np.linspace(-150, 150, size[0])
    x, y = np.meshgrid(x, y)
    z = np.exp(-(((x - mean) ** 2 + (y - mean) ** 2) / (2 * std_dev ** 2)))
    return z


def embed_patch_in_canvas(canvas, patch, position=(0, 0), patch_size=(300, 300)):
    canvas_height, canvas_width = 720, 1280
    patch_height, patch_width = patch_size
    pos_x, pos_y = position
    pos_x = max(0, min(pos_x, canvas_width))
    pos_y = max(0, min(pos_y, canvas_width))

    x1 = pos_x - patch_width // 2
    y1 = pos_y - patch_height // 2
    x2 = pos_x + patch_width // 2
    y2 = pos_y + patch_height // 2
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(canvas_width, x2)
    y2 = min(canvas_height, y2)
    embed_w = x2 - x1
    embed_h = y2 - y1
    if embed_w <= 0 or embed_h <= 0:
        logger.warning(f'Cannot embed patch in canvas: ({position})')
        return canvas
    if embed_w < patch_width or embed_h < patch_height:
        _patch = patch[:embed_h, :embed_w]
    else:
        _patch = patch
    # Embed the patch in the canvas
    canvas[y1:y2, x1:x2] += _patch
    return canvas


class Agent:
    GAUSSIAN = generate_gaussian_patch()
    OBSERVE_THRESHOLD = 0.6
    # --------------------------------------------------------------------------------

    def __init__(self, strategy: dict = None):
        self.z = np.zeros((720, 1280), dtype=np.float32)
        self.focus: Focus = None
        # 
        strategy: dict = strategy if strategy is not None else {
            # 'weights': [1., 1., 1., 0.6, 0.3, 0.3],
            'priorities': [],
            'invite_friend': False,
            'auto_bean': False
        }
        self.strategy = strategy
        self.weights: list[float] = strategy.get('weights', [1., 1., 0.7, 0.3, 0., 0.])
        self.priorities: list[int] = strategy.get('priorities', [])
        self.invite_friend: bool = strategy.get('invite_friend', False)
        self.auto_bean: bool = strategy.get('auto_bean', False)
        #
        self.last_throw_time = datetime.now()
        self.dbg_throw: int = 0
        self.dbg_throw_n: int = 0

    @classmethod
    def gamma(cls, tracks: list[tuple],
              weights: list[float],
              priorities: list[int] = []) -> np.ndarray:
        """
        @param tracks:
        @param weights: sp, ssr, sr, r, n, g
        @param priorities:
        @return:
        """
        z = np.zeros((720, 1280), dtype=np.float32)
        for _id, _class, _conf, _cx, _cy, _w, _h, _v in tracks:
            weight = 1.
            mu = 0.8 + (_cx * 0.2) / 1280
            match _class:
                case _ if CI.MIN_G <= _class <= CI.MAX_G: weight = weights[5]
                case _ if CI.MIN_N <= _class <= CI.MAX_N: weight = weights[4]
                case _ if _class != CI.R_008 and _class != CI.R_007 and (CI.MIN_R <= _class <= CI.MAX_R):
                    weight = weights[3]  # 不要童男童女
                case _ if CI.MIN_SR <= _class <= CI.MAX_SR: weight = weights[2]
                case _ if CI.MIN_SSR <= _class <= CI.MAX_SSR: weight = 1.5 * weights[1]
                case _ if CI.MIN_SP <= _class <= CI.MAX_SP: weight = 1.5 * weights[0]
                case CI.BUFF_005:  # freeze
                    weight = -1.
                    _cy += 100
                case _: continue
            for priority in priorities:  # 我的代码在你之上
                if priority == _class:
                    weight = 1.7
                    break
            if weight == 0.:
                continue
            z = embed_patch_in_canvas(canvas=z, patch=(mu * weight) * Agent.GAUSSIAN, position=(_cx, _cy))
        return z

    @classmethod
    def argmax_gamma(cls, z: np.ndarray, tracks: list[tuple]) -> Focus:
        max_y, max_x = np.unravel_index(np.argmax(z), z.shape)
        max_variance = 2000
        max_index = -1
        for index, track in enumerate(tracks):
            _id, _class, _conf, _cx, _cy, _w, _h, _v = track
            variance = (max_x - _cx)**2 + (max_y - _cy)**2
            if variance < max_variance:
                max_index = index
                max_variance = variance
        return Focus(inputs=tracks[max_index])

    def decision(self, tracks: list[tuple], state: list) -> list:
        not_decision = [-1, -1, False, -1]
        if not tracks:
            return not_decision
        # Cache the time interval for scattering beans
        new_time = datetime.now()
        delta_time = 1000 * (new_time - self.last_throw_time).total_seconds()  # ms
        self.check_observe(tracks=tracks)
        if self.focus is None:
            return not_decision
        result = self.focus.decision(tracks=tracks, strategy=self.strategy, state=[delta_time] + state)
        if result[2]:
            self.last_throw_time = new_time
            self.dbg_throw += 1
        else:
            self.dbg_throw_n += 1
        return result

    def check_observe(self, tracks: list[tuple]):
        z = Agent.gamma(tracks=tracks, weights=self.weights, priorities=self.priorities)
        focus = Agent.argmax_gamma(z=z, tracks=tracks)
        omega = focus.omega(z)
        if omega < self.OBSERVE_THRESHOLD:
            if self.focus is not None:
                logger.info(f'Focus disappear')
            self.focus = None
            return
        if self.focus is None or self.focus != focus:
            logger.info(f'Focus changed, now: {id2name(focus._class)}')
            self.focus = focus
            self.focus.set_omega(omega)
        elif self.focus == focus:
            self.focus.update(focus)
            self.focus.set_omega(omega)
        # if Debugger.info_enable:
        #     self.focus.show()

