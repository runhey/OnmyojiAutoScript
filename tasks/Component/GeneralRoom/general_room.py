# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
import random
import cv2
import numpy as np

from random import randint

from tasks.Component.GeneralRoom.assets import GeneralRoomAssets
from module.atom.ocr import RuleOcr
from module.atom.image import RuleImage
from tasks.base_task import BaseTask
from module.logger import logger
from module.base.timer import Timer


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
        click_number = 0
        while 1:
            self.screenshot()
            if click_number > 3:
                logger.warning('Create room button do not take effect')
                logger.warning('The most possible reason is that there are not challenge tickets')
                return False
            if self.appear_then_click(self.I_CREATE_ROOM, interval=2):
                click_number += 1
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
            if self.appear_then_click(self.I_ENSURE_PRIVATE_FALSE, interval=1):
                continue
            if self.appear_then_click(self.I_ENSURE_PRIVATE_FALSE_2, interval=1):
                continue

    def ensure_public(self) -> bool:
        """
        确认公开房间， 允许任何人加入
        :return:
        """
        logger.info('Ensure public')
        while 1:
            self.screenshot()
            if self.appear(self.I_ENSURE_PUBLIC):
                return True
            if self.appear(self.I_ENSURE_PUBLIC_2):
                return True
            if self.appear_then_click(self.I_ENSURE_PUBLIC_FALSE, interval=1):
                continue
            if self.appear_then_click(self.I_ENSURE_PUBLIC_FALSE_2, interval=1):
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

    def exit_team(self) -> bool:
        """
        在组队界面 退出组队的界面， 返回到庭院或者是你一开始进入的入口
        :return:
        """
        if self.appear(self.I_CHECK_TEAM):
            logger.info('Exit team ui')
            while 1:
                self.screenshot()
                if not self.appear(self.I_CHECK_TEAM):
                    return True
                if self.appear_then_click(self.I_GR_BACK_YELLOW, interval=0.5):
                    continue

    def check_zones(self, name: str) -> bool:
        """
        确认副本的名称，并选中
        :param name:
        :return:
        """
        pos = self.list_find(self.L_TEAM_LIST, name)
        if not pos:
            return False
        if name == '愤怒的石距' or name == '喷怒的石距':
            name = '价悠的石距'
        self.O_GR_ZONES_NAME.keyword = name
        click_timer = Timer(1.1)
        click_timer.start()
        while 1:
            self.screenshot()

            if self.ocr_appear(self.O_GR_ZONES_NAME):
                break
            # https://github.com/runhey/OnmyojiAutoScript/issues/488
            # 只能说朴实无华
            text_ocr = self.O_GR_ZONES_NAME.ocr(self.device.image)
            if name == '石距' and name in text_ocr:
                break
            if name == '金币妖怪' and "金币" in text_ocr:
                break
            if click_timer.reached():
                click_timer.reset()
                self.device.click(x=pos[0] + randint(-5, 5), y=pos[1] + randint(-5, 5))

        return True

