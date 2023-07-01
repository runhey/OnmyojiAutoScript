# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import cv2
import numpy as np

from tasks.Component.GeneralRoom.assets import GeneralRoomAssets
from module.atom.ocr import RuleOcr
from module.atom.image import RuleImage
from tasks.base_task import BaseTask
from module.logger import logger


class GeneralRoom(BaseTask, GeneralRoomAssets):

    def create_room(self) -> bool:
        """
        创建队伍  一般是下方的黄色按钮
        :return:
        """
        logger.info('Create room')
        if not self.appear(self.I_CREATE_ROOM):
            logger.warning('No create room button')
            return False
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_CREATE_ROOM, interval=2):
                continue
            if self.appear(self.I_CREATE_ENSURE):
                return True
            if self.appear(self.I_CREATE_ENSURE_2):
                return True

    def ensure_private(self) -> bool:
        """
        确认私人房间, 不公开仅邀请
        :return:
        """
        logger.info('Ensure private')
        while 1:
            self.screenshot()
            if self.appear(self.I_ENSURE_PRIVATE):
                return True
            if self.appear(self.I_ENSURE_PRIVATE_2):
                return True
            if self.appear_then_click(self.I_ENSURE_PRIVATE_FALSE):
                continue
            if self.appear_then_click(self.I_ENSURE_PRIVATE_FALSE_2):
                continue

    def create_ensure(self) -> bool:
        """
        创建确认
        :return:
        """
        logger.info('Create ensure')
        appear1 = self.I_CREATE_ENSURE.match(self.device.image)
        appear2 = self.I_CREATE_ENSURE_2.match(self.device.image)
        target = None
        if appear1:
            target = self.I_CREATE_ENSURE
        elif appear2:
            target = self.I_CREATE_ENSURE_2
        if not target:
            logger.warning('No create ensure button')
            return False

        while 1:
            self.screenshot()
            if self.appear_then_click(target, interval=1.5):
                continue
            if not self.appear(target):
                return True

