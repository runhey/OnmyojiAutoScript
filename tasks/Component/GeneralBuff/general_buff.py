# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import cv2
import numpy as np

from tasks.Component.GeneralBuff.assets import GeneralBuffAssets
from module.atom.ocr import RuleOcr
from module.atom.image import RuleImage
from tasks.base_task import BaseTask
from module.logger import logger


class GeneralBuff(BaseTask, GeneralBuffAssets):

    def open_buff(self):
        """
        打开buff的总界面
        :return:
        """
        logger.info('Open buff')
        while 1:
            self.screenshot()
            if self.appear(self.I_CLOUD):
                break
            if self.appear_then_click(self.I_BUFF_1, interval=2):
                continue

        check_image = self.I_AWAKE
        while 1:
            self.screenshot()
            if self.appear(check_image):
                break

            self.swipe(self.S_BUFF_UP, interval=2)

    def close_buff(self):
        """
        关闭buff的总界面, 但是要确保buff界面已经打开了
        :return:
        """
        logger.info('Close buff')
        while 1:
            self.screenshot()
            if not self.appear(self.I_CLOUD):
                break
            if self.appear_then_click(self.I_BUFF_1, interval=2):
                continue

    @staticmethod
    def get_area(image: np.array, buff: RuleOcr) -> tuple:
        """
        获取要点击的开关buff的区域
        :param cls:
        :param image:
        :param buff:
        :return:  如果没有就返回None
        """
        area = buff.ocr(image)
        if area == tuple([0, 0, 0, 0]):
            logger.info('No gold 50 buff')
            return None

        # 开始的x坐标就是文字的右边
        start_x = area[0] + area[2] + 10  # 10是文字和开关之间的间隔
        start_y = area[1] - 10
        width = 80  # 开关的宽度 80够了
        height = area[3] + 20
        return int(start_x), int(start_y), int(width), int(height)

    def set_switch_area(self, area):
        """
        设置开关的区域
        :param area:
        :return:
        """
        self.I_OPEN_YELLOW.roi_back = list(area)  # 动态设置roi
        self.I_CLOSE_RED.roi_back = list(area)


    def gold_50(self, is_open: bool = True):
        """
        金币50buff
        :param is_open: 是否打开
        :return:
        """
        logger.info('Gold 50 buff')
        self.screenshot()
        area = self.get_area(self.device.image, self.O_GOLD_50)
        if not area:
            logger.warning('No gold 100 buff')
            return None
        self.I_OPEN_YELLOW.roi_back = list(area)  # 动态设置roi
        self.I_CLOSE_RED.roi_back = list(area)
        if is_open:
            while 1:
                self.screenshot()
                if self.appear(self.I_OPEN_YELLOW):
                    break
                if self.appear_then_click(self.I_CLOSE_RED, interval=1):
                    continue
        else:
            while 1:
                self.screenshot()
                if self.appear(self.I_CLOSE_RED):
                    break
                if self.appear_then_click(self.I_OPEN_YELLOW, interval=1):
                    continue

    def gold_100(self, is_open: bool = True):
        """
        金币100buff
        :param is_open: 是否打开
        :return:
        """
        logger.info('Gold 100 buff')
        self.screenshot()
        area = self.get_area(self.device.image, self.O_GOLD_100)
        if not area:
            logger.warning('No gold 100 buff')
            return None
        self.I_OPEN_YELLOW.roi_back = list(area)
        self.I_CLOSE_RED.roi_back = list(area)
        if is_open:
            while 1:
                self.screenshot()
                if self.appear(self.I_OPEN_YELLOW):
                    break
                if self.appear_then_click(self.I_CLOSE_RED, interval=1):
                    continue
        else:
            while 1:
                self.screenshot()
                if self.appear(self.I_CLOSE_RED):
                    break
                if self.appear_then_click(self.I_OPEN_YELLOW, interval=1):
                    continue

    def exp_50(self, is_open: bool = True):
        """
        经验50buff
        :param is_open: 是否打开
        :return:
        """
        logger.info('Exp 50 buff')
        self.screenshot()
        area = self.get_area(self.device.image, self.O_EXP_50)
        if not area:
            logger.warning('No gold 100 buff')
            return None
        self.I_OPEN_YELLOW.roi_back = list(area)
        self.I_CLOSE_RED.roi_back = list(area)
        if is_open:
            while 1:
                self.screenshot()
                if self.appear(self.I_OPEN_YELLOW):
                    break
                if self.appear_then_click(self.I_CLOSE_RED, interval=1):
                    continue
        else:
            while 1:
                self.screenshot()
                if self.appear(self.I_CLOSE_RED):
                    break
                if self.appear_then_click(self.I_OPEN_YELLOW, interval=1):
                    continue

    def exp_100(self, is_open: bool = True):
        """
        经验100buff
        :param is_open: 是否打开
        :return:
        """
        logger.info('Exp 100 buff')
        while 1:
            self.screenshot()
            area = self.get_area(self.device.image, self.O_EXP_100)
            if not area:
                logger.warning('No gold 100 buff')
                continue
            self.set_switch_area(area)

            if not self.appear(self.I_OPEN_YELLOW) and not self.appear(self.I_CLOSE_RED):
                logger.info('No exp 100 buff')
                self.device.swipe(p2=(530, 240), p1=(580, 320))
                time.sleep(1)
            else:
                break

        if is_open:
            while 1:
                self.screenshot()
                if self.appear(self.I_OPEN_YELLOW):
                    break
                if self.appear_then_click(self.I_CLOSE_RED, interval=1):
                    continue
        else:
            while 1:
                self.screenshot()
                if self.appear(self.I_CLOSE_RED):
                    break
                if self.appear_then_click(self.I_OPEN_YELLOW, interval=1):
                    continue

    @staticmethod
    def get_area_image(image: np.array, target: RuleImage) -> list:
        """
        获取觉醒加成或者是御魂加成所要点击的区域
        因为实在的图片比ocr快
        :param image:
        :param target:
        :return:
        """
        if not target.match(image):
            logger.warning(f'No {target.name} buff')
            return None
            # logger.info(f'front area: {target.roi_front}')
            # logger.info(f'front center: {target.front_center()}')
        start_x = int(target.front_center()[0] + 364)
        start_y = int(target.roi_front[1])
        width = 80
        height = int(target.roi_front[3])
        return [start_x, start_y, width, height]

    def awake(self, is_open: bool = True):
        """
        觉醒buff
        :param is_open: 是否打开
        :return:
        """
        logger.info('Awake buff')
        self.screenshot()
        area = self.get_area_image(self.device.image, self.I_AWAKE)
        if not area:
            logger.warning('No awake buff')
            return None
        self.set_switch_area(area)
        if is_open:
            while 1:
                self.screenshot()
                if self.appear(self.I_OPEN_YELLOW):
                    break
                if self.appear_then_click(self.I_CLOSE_RED, interval=1):
                    continue
        else:
            while 1:
                self.screenshot()
                if self.appear(self.I_CLOSE_RED):
                    break
                if self.appear_then_click(self.I_OPEN_YELLOW, interval=1):
                    continue

    def soul(self, is_open: bool = True):
        """
        御魂buff
        :param is_open: 是否打开
        :return:
        """
        logger.info('Soul buff')
        self.screenshot()
        area = self.get_area_image(self.device.image, self.I_SOUL)
        if not area:
            logger.warning('No soul buff')
            return None
        self.set_switch_area(area)
        if is_open:
            while 1:
                self.screenshot()
                if self.appear(self.I_OPEN_YELLOW):
                    break
                if self.appear_then_click(self.I_CLOSE_RED, interval=1):
                    continue
        else:
            while 1:
                self.screenshot()
                if self.appear(self.I_CLOSE_RED):
                    break
                if self.appear_then_click(self.I_OPEN_YELLOW, interval=1):
                    continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = GeneralBuff(c, d)

    t.open_buff()
    # t.screenshot()
    #
    t.awake(is_open=True)
    t.soul(is_open=True)
    # t.gold_50(is_open=True)
    t.gold_100(is_open=True)
    t.exp_50(is_open=True)
    t.exp_100(is_open=True)



