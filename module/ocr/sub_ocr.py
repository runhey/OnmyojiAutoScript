# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

import cv2
import re
import cn2an

from datetime import timedelta

from module.ocr.ppocr import TextSystem
from module.exception import ScriptError
from module.base.utils import area_pad, crop, float2str
from module.ocr.base_ocr import BaseCor, OcrMode, OcrMethod
from module.ocr.utils import merge_area
from module.logger import logger


class Full(BaseCor):
    """
    这个类适用于大ROI范围的文本识别。可以支持多条文本识别， 默认不支持竖方向的文本识别
    """
    def after_process(self, result):
        return result

    def ocr_full(self, image, keyword: str=None) -> tuple:
        """
        检测整个图片的文本,并对结果进行过滤。返回的是匹配到的keyword的左边。如果没有匹配到返回(0, 0, 0, 0)
        :param image:
        :param keyword:
        :return:
        """
        if keyword is None:
            keyword = self.keyword

        boxed_results = self.detect_and_ocr(image)
        if not boxed_results:
            return 0, 0, 0, 0

        index_list = self.filter(boxed_results, keyword)
        logger.info(f"OCR [{self.name}] detected in {index_list}")
        # 如果一个都没有匹配到
        if not index_list:
            return 0, 0, 0, 0

        # 如果匹配到了多个,则合并所有的坐标，返回合并后的坐标
        if len(index_list) > 1:
            area_list = [(
                boxed_results[index].box[0, 0],  # x
                boxed_results[index].box[0, 1],  # y
                boxed_results[index].box[1, 0] - boxed_results[index].box[0, 0],     # width
                boxed_results[index].box[2, 1] - boxed_results[index].box[0, 1],     # height
            ) for index in index_list]
            area = merge_area(area_list)
            self.area = area[0]+self.roi[0], area[1]+self.roi[1], area[2], area[3]
        else:
            box = boxed_results[index_list[0]].box
            self.area = box[0, 0]+self.roi[0], box[0, 1]+self.roi[1], box[1, 0] - box[0, 0], box[2, 1] - box[0, 1]

        logger.info(f"OCR [{self.name}] detected in {self.area}")
        return self.area

class Single(BaseCor):
    """
    这个类使用于单行文本识别（所识别的ROI不会动）
    """
    def after_process(self, result):
        return result

    def ocr_single(self, image) -> str:
        """
        检测某个固定位置的roi的文本。可以是横方向也可以是竖方向
        :param image:
        :return: 返回到识别的文字, 如果没有返回空字符串
        """
        if self.roi:
            result = self.ocr_single_line(image)
            if result != "":
                return result

            # 如果没有识别到，这个时候考虑到可能是竖方向的文本, 使用detect_and_ocr来进行识别
            logger.info(f"[{self.name}] Try to detect vertically")
            result = self.detect_and_ocr(image)
            if not result:
                logger.info(f"[{self.name}]: No text detected in ROI")
                return ""
            if result[0].ocr_text != "" and result[0].score > self.score:
                return result[0].ocr_text

            # 如果还是没有识别到。那可能就是真的没有识别到了
            return ""
        else:
            raise ScriptError("Roi is empty")

class Digit(Single):

    def after_process(self, result):
        result = super().after_process(result)
        result = result.replace('I', '1').replace('D', '0').replace('S', '5')
        result = result.replace('B', '8').replace('？', '2').replace('?', '2')
        result = result.replace('d', '6')
        result = [char for char in result if char.isdigit()]
        result = ''.join(result)

        prev = result
        result = int(result) if result else 0
        if str(result) != prev:
            logger.warning(f'OCR {self.name}: Result "{prev}" is revised to "{result}"')

        return result

    def ocr_digit(self, image) -> int:
        """
        返回数字
        :param image:
        :return:
        """
        result = self.ocr_single(image)

        if result == "":
            return 0
        else:
            return int(result)

class DigitCounter(Single):
    def after_process(self, result):
        result = super().after_process(result)
        result = result.replace('I', '1').replace('D', '0').replace('S', '5')
        result = result.replace('B', '8').replace('？', '2').replace('?', '2')
        result = result.replace('d', '6')
        result = [char for char in result if char.isdigit() or char == '/']
        result = ''.join(result)
        return result

    @classmethod
    def ocr_str_digit_counter(cls, result: str) -> tuple[int, int, int]:
        result = re.search(r'(\d+)/(\d+)', result)
        if result:
            result = [int(s) for s in result.groups()]
            current, total = int(result[0]), int(result[1])
            # 不知道为什么加了这一句，妈的
            # current = min(current, total)
            if current > total:
                logger.warning(f'[{cls.name}]: Current {current} is greater than total {total}')
            return current, total - current, total
        else:
            logger.warning(f'Unexpected ocr result: {result}')
            return 0, 0, 0


    def ocr_digit_counter(self, image) -> tuple[int, int, int]:
        """
        获取计数的结果
        :param image:
        :return: 例如 14/15，返回 (14, 1, 15) 。如果没有识别到，返回 (0, 0, 0)
        """
        result = self.ocr_single(image)
        if result == "":
            return 0, 0, 0
        return self.ocr_str_digit_counter(result)

class Duration(Single):
    def after_process(self, result):
        result = result.replace('I', '1').replace('D', '0').replace('S', '5')
        result = result.replace('o', '0').replace('l', '1').replace('O', '0')
        result = result.replace('B', '8').replace('：', ':').replace(' ', '').replace('.', ':')
        result = super().after_process(result)
        return result

    @staticmethod
    def parse_time(string):
        """
        Args:
            string (str): `01:30:00`

        Returns:
            datetime.timedelta:
        """
        result = re.search(r'(\d{1,2}):?(\d{2}):?(\d{2})', string)
        if result:
            result = [int(s) for s in result.groups()]
            return timedelta(hours=result[0], minutes=result[1], seconds=result[2])
        else:
            logger.warning(f'Invalid duration: {string}')
            return timedelta(hours=0, minutes=0, seconds=0)

    def ocr_duration(self, image) -> timedelta:
        """

        :param image:
        :return:
        """
        result = self.ocr_single(image)

        if result == "":
            return timedelta(hours=0, minutes=0, seconds=0)

        return self.parse_time(result)

class Quantity(BaseCor):
    """
    专门用于识别超级多的数量，不支持多个区域的识别
    可支持负数
    比如：”6.33亿“ ”1.2万“ “53万/100” -> 530,000
    """
    def after_process(self, result):
        result = super().after_process(result)
        result = result.replace('I', '1').replace('D', '0').replace('S', '5')
        result = result.replace('B', '8').replace('？', '2').replace('?', '2').replace('d', '6')
        result = [char
                  for char in result
                  if char.isdigit() or char == '.' or char == '/' or char == '万' or char == '亿' or char == '千']
        result = ''.join(result)

        if '/' in result:
            result_split = result.split('/')
            result = result_split[0]
        result = cn2an.cn2an(result, 'smart')

        try:
            result = int(result)
        except ValueError:
            logger.warning(f'[{self.name}]: Invalid quantity: {result}')
            result = 0
        return result

    def ocr_quantity(self, image) -> int:
        """
        返回数量
        :param image:
        :return:
        """
        boxed_results = self.detect_and_ocr(image)
        if not boxed_results:
            logger.warning(f'[{self.name}]: No text detected')
            return 0

        box = boxed_results[0].box
        self.area = box[0, 0] + self.roi[0], box[0, 1] + self.roi[1], box[1, 0] - box[0, 0], box[2, 1] - box[0, 1]
        return boxed_results[0].ocr_text



if __name__ == '__main__':
    import cv2
    image = cv2.imread(r'E:\Project\OnmyojiAutoScript-assets\jade.png')

