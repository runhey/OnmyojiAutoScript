import cv2
import time
import copy
import numpy as np

from datetime import datetime
from pathlib import Path
from numpy import uint8, fromfile

from oashya.tracker import Tracker
from module.logger import logger


def generate_gaussian_patch(size=(300, 300), mean=0, std_dev=60):
    x = np.linspace(-150, 150, size[1])
    y = np.linspace(-150, 150, size[0])
    x, y = np.meshgrid(x, y)
    z = np.exp(-(((x - mean) ** 2 + (y - mean) ** 2) / (2 * std_dev ** 2)))
    return z


def embed_patch_in_canvas(canvas, patch, position=(0, 0), patch_size=(300, 300)):
    canvas_height, canvas_width = 720, 1280
    patch_height, patch_width = patch_size

    x1 = position[0] - patch_width // 2
    y1 = position[1] - patch_height // 2
    x2 = position[0] + patch_width // 2
    y2 = position[1] + patch_height // 2
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(canvas_width, x2)
    y2 = min(canvas_height, y2)
    embed_w = x2 - x1
    embed_h = y2 - y1
    if embed_w < patch_width or embed_h < patch_height:
        _patch = patch[:embed_h, :embed_w]
    else:
        _patch = patch
    # Embed the patch in the canvas
    canvas[y1:y2, x1:x2] += _patch
    return canvas




class Agent:
    GAUSSIAN = generate_gaussian_patch()
    MIN_BUFF: int = 0
    MAX_BUFF: int = 6
    MIN_N: int = 7
    MAX_N: int = 18
    MIN_G: int = 19
    MAX_G: int = 35
    MIN_R: int = 36
    MAX_R: int = 72
    MIN_SR: int = 73
    MAX_SR: int = 137
    MIN_SSR: int = 138
    MAX_SSR: int = 183
    MIN_SP: int = 184
    MAX_SP: int = 218
    BUFF_001 = 0
    BUFF_002 = 1
    BUFF_003 = 2
    BUFF_004 = 3
    BUFF_005 = 4
    BUFF_006 = 5
    BUFF_007 = 6

    @classmethod
    def gamma(cls, tracks: list[tuple],
              weights: list[float] = [1., 1., 1., .6, 0.3, 0.3],
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
            match _class:
                case _ if cls.MIN_G <= _class <= cls.MAX_G: weight = weights[5]
                case _ if cls.MIN_N <= _class <= cls.MAX_N: weight = weights[4]
                case _ if cls.MIN_R <= _class <= cls.MAX_R: weight = weights[3]
                case _ if cls.MIN_SR <= _class <= cls.MAX_SR: weight = weights[2]
                case _ if cls.MIN_SSR <= _class <= cls.MAX_SSR: weight = weights[1]
                case _ if cls.MIN_SP <= _class <= cls.MAX_SP: weight = weights[0]
                case cls.BUFF_005: weight = -1.  # freeze
            z = embed_patch_in_canvas(canvas=z, patch=weight * Agent.GAUSSIAN, position=(_cx, _cy))
        return z





