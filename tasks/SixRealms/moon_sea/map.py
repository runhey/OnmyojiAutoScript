import cv2
import re
import numpy as np
from numpy import uint8, fromfile
from module.logger import logger

from tasks.base_task import BaseTask
from tasks.SixRealms.moon_sea.skills import MoonSeaSkills
from tasks.SixRealms.assets import SixRealmsAssets
from tasks.SixRealms.common import MoonSeaType
from tasks.SixRealms.oas_ocr import StoneOcr


class MoonSeaMap(MoonSeaSkills):
    map_ocr = StoneOcr(
        roi=(0, 0, 1280, 720),
        area=(0, 0, 1280, 720),
        mode="Full",
        method="Default",
        keyword="",
        name="map_ocr")

    @staticmethod
    def contains_any_char(string, chars):
        return not set(string).isdisjoint(set(chars))

    def decide(self) -> tuple:
        """
        这个玩意，检测不是很准
        @return: 岛屿的类型，剩余多少回合, (x，y, w, h)
        """
        self.screenshot()
        if self.appear(self.I_BOSS_FIRE):
            # 最后的boss
            return MoonSeaType.island106, 0, (0, 0, 0, 0)
        isl_type = MoonSeaType.island100
        isl_roi = (0, 0, 0, 0)
        isl_num = 0
        results = self.map_ocr.detect_and_ocr(image=self.device.image)
        rx1, ry1, rw, rh = self.O_OCR_MAP.roi
        rx2, ry2 = rx1 + rw, ry1 + rh
        for result in results:
            # box 是四个点坐标 左上， 右上， 右下， 左下
            x1, y1, x2, y2 = result.box[0][0], result.box[0][1], result.box[2][0], result.box[2][1]
            w, h = x2 - x1, y2 - y1
            text = result.ocr_text

            if self.contains_any_char(result.ocr_text, chars='回合国') and \
                    (x1 > 1000 and y1 + h < 300):
                # if text[1].isdigit():
                #     isl_num = int(text[:2])
                # elif text[0].isdigit():
                #     isl_num = int(text[0])
                match = re.search(r'\d{1,2}', text)
                if match:
                    isl_num = int(match.group())
            if x1 < rx1 or x2 > rx2 or y1 < ry1 or y2 > ry2:
                continue
            if isl_type == MoonSeaType.island100 and self.contains_any_char(result.ocr_text, chars='宁息'):
                # 如果身上没有达到300块钱就不去了
                if self.appear(self.I_M_STORE):
                    continue
                isl_type = MoonSeaType.island101
                isl_roi = x1, y1, w, h
            elif isl_type == MoonSeaType.island100 and self.contains_any_char(result.ocr_text, chars='神秘'):
                isl_type = MoonSeaType.island102
                isl_roi = x1, y1, w, h
            elif isl_type == MoonSeaType.island100 and self.contains_any_char(result.ocr_text, chars='回混范'):
                isl_type = MoonSeaType.island103
                isl_roi = x1, y1, w, h
            elif isl_type == MoonSeaType.island100 and self.contains_any_char(result.ocr_text, chars='蜜馨屡战'):
                isl_type = MoonSeaType.island104
                isl_roi = x1, y1, w, h
            elif isl_type == MoonSeaType.island100 and self.contains_any_char(result.ocr_text, chars='星之'):
                isl_type = MoonSeaType.island105
                isl_roi = x1, y1, w, h
        logger.info('Island type: {}, Residue: {}, ROI: {}'.format(isl_type, isl_num, isl_roi))
        return isl_type, isl_num, isl_roi

    def enter_island(self, isl_type, isl_roi):
        if isl_type == MoonSeaType.island100:
            logger.warning('The island type was not recognized')
            logger.warning('Pick one at random, starting from the right')
            while 1:
                self.screenshot()
                if not self.in_main() and self.appear(self.I_BACK_EXIT):
                    break
                if self.appear_then_click(self.I_UI_CANCEL, interval=1):
                    continue
                if self.click(self.C_ISLAND_ENTER_1, interval=2):
                    continue
                if self.click(self.C_ISLAND_ENTER_2, interval=2):
                    continue
                if self.click(self.C_ISLAND_ENTER_3, interval=2):
                    continue
                if self.click(self.C_ISLAND_ENTER_4, interval=2):
                    continue
                if self.click(self.C_ISLAND_ENTER_5, interval=2):
                    continue
                if self.click(self.C_ISLAND_ENTER_6, interval=2):
                    continue
            logger.info('Entering island randomly')
            return
        isl_roi = [isl_roi[0]-40, isl_roi[1] + 70, isl_roi[2] + 40, isl_roi[3]+40]
        self.C_ISLAND_ENTER.roi_front = isl_roi
        while 1:
            self.screenshot()
            if not self.in_main() and self.appear(self.I_BACK_EXIT):
                break
            if self.click(self.C_ISLAND_ENTER, interval=2.5):
                continue
        logger.info('Entering island')
        return

    def activate_store(self) -> bool:
        """
        最后打boss前面激活一次商店买东西
        @return: 有钱够就是True
        """
        logger.info('Activating store')
        self.screenshot()
        if self.appear(self.I_M_STORE) and not self.appear(self.I_M_STORE_ACTIVITY):
            logger.warning('Now you have not money to buy items')
            logger.warning('Store is not active')
            return False
        cnt_act = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_UI_CONFIRM):
                self.ui_click_until_disappear(self.I_UI_CONFIRM, interval=2)
                break
            if cnt_act >= 3:
                logger.warning('Store is not active')
                return False
            if self.appear_then_click(self.I_M_STORE_ACTIVITY, interval=1.5):
                cnt_act += 1
                continue

    def entry_island_random(self, area: list = None):
        """

        :param area: 搁置
        :return:
        """
        # if not isinstance(area, list):
        #     area = list(area)
        logger.info('Entry island randomly')
        while 1:
            self.screenshot()
            if not self.in_main() and self.appear(self.I_BACK_EXIT):
                break
            if self.click(self.C_ISLAND_ENTER_4, interval=2):
                continue
            if self.click(self.C_ISLAND_ENTER_5, interval=2):
                continue
            if self.click(self.C_ISLAND_ENTER_6, interval=2):
                continue
        return


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from module.base.utils import load_image

    c = Config('oas1')
    d = Device(c)
    t = MoonSeaMap(c, d)
    t.device.image = load_image(r'C:\Users\Ryland\Desktop\Desktop\34.png')

    match = re.search(r'\d{1,2}', '<17回合后迎战月读')
    if match:
        isl_num = int(match.group())
        print(isl_num)

