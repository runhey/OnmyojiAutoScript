import re
from module.atom.click import RuleClick
from module.base.timer import Timer
from module.exception import GameStuckError
from module.logger import logger

from tasks.SixRealms.moon_sea.skills import MoonSeaSkills
from tasks.SixRealms.assets import SixRealmsAssets
from tasks.SixRealms.common import MoonSeaType
from tasks.SixRealms.oas_ocr import StoneOcr


class MoonSeaMap(MoonSeaSkills):
    island_markers = {
        MoonSeaType.island101: SixRealmsAssets.I_ISLAND_MARKER_101,
        MoonSeaType.island102: SixRealmsAssets.I_ISLAND_MARKER_102,
        MoonSeaType.island103: SixRealmsAssets.I_ISLAND_MARKER_103,
        MoonSeaType.island104: SixRealmsAssets.I_ISLAND_MARKER_104,
        MoonSeaType.island105: SixRealmsAssets.I_ISLAND_MARKER_105,
    }
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

    def _marker_boxes(self, kind):
        marker = self.island_markers[kind]
        return [tuple(match[1:]) for match in marker.match_all_any(self.device.image)]

    @staticmethod
    def _nearby_marker(boxes, roi):
        # 岛屿上下浮动。同类岛并排时，只跟踪原来那一列。
        center_x = roi[0] + roi[2] / 2
        nearest = min(boxes, key=lambda box: abs(box[0] + box[2] / 2 - center_x), default=None)
        if nearest and abs(nearest[0] + nearest[2] / 2 - center_x) <= 60:
            return nearest

    def decide(self, prefer_store=False) -> tuple:
        self.screenshot()
        if self.appear(self.I_BOSS_FIRE):
            # 最后的boss
            return MoonSeaType.island106, 0, (0, 0, 0, 0)
        kind, rounds, roi = self._read_map_ocr()
        candidates = {}
        for island in self.island_markers:
            if island == MoonSeaType.island101 and self.appear(self.I_M_STORE):
                continue
            boxes = self._marker_boxes(island)
            if boxes:
                candidates[island] = boxes
        if prefer_store and MoonSeaType.island101 in candidates:
            kind = MoonSeaType.island101
            roi = max(candidates[kind])
        elif kind in candidates:
            roi = self._nearby_marker(candidates[kind], roi) or max(candidates[kind])
        elif candidates:
            # 没有对应的 OCR 目标时，沿用从右向左的选岛顺序。
            kind, roi = max(((island, max(boxes)) for island, boxes in candidates.items()),
                            key=lambda candidate: candidate[1][0])
        logger.info('Island type: {}, Residue: {}, ROI: {}'.format(kind, rounds, roi))
        return kind, rounds, roi

    def _read_map_ocr(self):
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
        return isl_type, isl_num, isl_roi

    def enter_island(self, isl_type, isl_roi):
        if isl_type == MoonSeaType.island100:
            logger.warning('The island type was not recognized')
            logger.warning('Pick one at random, starting from the right')
            timeout = Timer(15).start()
            click_timer = Timer(1)
            entrances = (
                self.C_ISLAND_ENTER_1, self.C_ISLAND_ENTER_2, self.C_ISLAND_ENTER_3,
                self.C_ISLAND_ENTER_4, self.C_ISLAND_ENTER_5, self.C_ISLAND_ENTER_6,
            )
            entrance_index = 0
            while 1:
                self.screenshot()
                if not self.in_main() and self.appear(self.I_BACK_EXIT):
                    break
                if timeout.reached():
                    raise GameStuckError('Enter unknown island timeout')
                if not click_timer.reached():
                    continue
                if self.appear_then_click(self.I_UI_CANCEL, interval=1):
                    click_timer.reset()
                    continue
                self.click(entrances[entrance_index])
                entrance_index = (entrance_index + 1) % len(entrances)
                click_timer.reset()
            logger.info('Entering island randomly')
            return
        timeout = Timer(15).start()
        click_timer = Timer(2.5)
        while 1:
            self.screenshot()
            on_map = self.in_main()
            if not on_map and self.appear(self.I_BACK_EXIT):
                break
            if timeout.reached():
                raise GameStuckError(f'Enter {isl_type.name} timeout')
            if not on_map or not click_timer.reached():
                continue
            click_timer.reset()
            roi = self._nearby_marker(self._marker_boxes(isl_type), isl_roi)
            if not roi:
                kind, _, box = self._read_map_ocr()
                if kind != isl_type or not self._nearby_marker([box], isl_roi):
                    continue
                roi = box
            x, y, w, h = roi
            # 以当帧标牌中心为基准，落点在下方 15～75 像素。
            cx, cy = int(x + w / 2), int(y + h / 2) + 45
            click_area = (cx - 30, cy - 30, 60, 60)
            self.click(RuleClick(click_area, click_area, name='island_enter'))
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

