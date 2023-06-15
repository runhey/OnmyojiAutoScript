# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import numpy as np

from module.base.decorator import cached_property
from module.logger import logger
from module.atom.click import RuleClick


class RuleLongClick(RuleClick):

    def __init__(self, roi_front: tuple, roi_back: tuple, duration: int = 1000, name: str=None) -> None:
        """
        初始化
        :param roi_front:
        :param roi_back:
        :param duration:
        """
        if not name:
            name = 'long_click'
        super().__init__(roi_front, roi_back, name=name)
        self.duration = duration


