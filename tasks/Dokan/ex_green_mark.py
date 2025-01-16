import threading
from enum import Enum

import cv2
import numpy as np
from pydantic import BaseModel

from module.base.timer import Timer
from module.logger import logger
from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Dokan.utils import retry


#
# def green_marker_detector(func):
#     def wrapper(self, *args, **kwargs):
#         event = threading.Event()
#
#         def detect_green_marker(image):
#             hsv_image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
#             lower_green = np.array([67, 115, 110])
#             upper_green = np.array([80, 255, 232])
#             mask = cv2.inRange(hsv_image, lower_green, upper_green)
#             result = cv2.bitwise_and(image, image, mask=mask)
#             res = self.I_GREEN_MARKER.match(result)
#             return res
#
#         def emit_exists():
#             logger.info("Green marker detected!")
#             unpack_screenshot()
#             event.set()
#
#         def screenshot_and_detect():
#             self.just_screenshot()
#             exists = detect_green_marker(self.device.image)
#             if exists:
#                 emit_exists()
#             return self.device.image
#
#         def pack_screenshot():
#             self.just_screenshot = self.screenshot
#             self.screenshot = screenshot_and_detect
#
#         def unpack_screenshot():
#             self.screenshot = self.just_screenshot
#
#         def thread_run(self, detect_time=3, cb=None, cbargs=None):
#             logger.info("detect thread running...")
#             t = Timer(detect_time)
#             t.start()
#             while event.wait(detect_time):
#                 logger.info("detect thread quit")
#                 return
#             unpack_screenshot()
#             if cb:
#                 logger.info(f"didn't detect green mark ,start running callback with arg:{cbargs}")
#                 try:
#                     cb(**cbargs)
#                 except Exception as e:
#                     logger.error(f"callback error:{e}")
#
#         # wrapper
#         callback = kwargs.get('callback', None)
#         cbargs = kwargs.get('cbargs', None)
#         detect_time = kwargs.get('detect_time', 3.0)
#
#         if callback:
#             logger.info("Green marker detector running...")
#             pack_screenshot()
#         # green mark 函数的参数列表
#         kwarg_key = ['enable', 'mark_mode']
#         func_kwargs = {key: kwargs[key] for key in kwarg_key if key in kwargs}
#         if not event.is_set():
#             func(self, *args, **func_kwargs)
#
#         if callback:
#             thread = threading.Thread(target=thread_run, args=(self, detect_time, callback, cbargs), daemon=True)
#             thread.start()
#         return
#
#     return wrapper


class GreenMarkState(int, Enum):
    #
    NOT_INIT = 0,
    INITED = 1,
    # 备用
    MARKED = 2,
    DISAPPEARED = 3


class ExtendGreenMark(GeneralBattle):
    # 式神名称
    _shikigami_name = ""
    # 绿标检测范围，x,y,w,h
    _green_mark_detect_area: list[int] = None
    # 式神名称范围，OCR检测出的式神名位置，x,y,w,h
    _green_mark_click_roi: list[int] = None
    # 绿标消失临界值
    MAX_DISAPPEAR_COUNT = 40
    MAX_DISAPPEAR_TIME = 4
    # 尝试生成绿标的间隔
    GREEN_MARK_INTERVAL = 1
    # 绿标消失后，screenshot的次数
    _disappear_count = 0
    # 绿标消失的时间
    _disappear_timer = Timer(MAX_DISAPPEAR_TIME)
    # 判断是否开始检测绿标
    _state = GreenMarkState.NOT_INIT

    #

    def __init__(self, config, device):
        super().__init__(config, device)
        self.super_green_mark = self.green_mark

    def init_green_mark_from_cfg(self, names: str = None, green_mark_type: GreenMarkType = None):
        self._shikigami_name = names
        if self._shikigami_name is None or self._shikigami_name == "":
            # 使用默认的绿标模式
            tmp = self.generate_green_mark_area(green_mark_type)
            self._green_mark_click_roi = tmp.roi_front
        else:
            # 使用式神名称进行绿标
            def detect_name_position_retry():
                self.device.screenshot()
                return self.detect_name_position(self.device.image, self._shikigami_name)

            # 多试几次，避免识别失败
            self._green_mark_click_roi = retry(detect_name_position_retry, 3)

        #
        self._green_mark_detect_area = self.calc_green_mark_locate_area(self._green_mark_click_roi)
        self.start_green_mark()
        return

    # @green_marker_detector
    # def ex_green_mark(self, enable=True, mark_mode=GreenMarkType.GREEN_MAIN):
    #     if not enable:
    #         return
    #     return self.super_green_mark(enable=enable, mark_mode=mark_mode)
    #
    # def ex_green_mark_3_retry(self, enable=True, mark_mode=GreenMarkType.GREEN_MAIN):
    #     if not enable:
    #         return
    #     return self.ex_green_mark(enable=enable, mark_mode=mark_mode, detect_time=3, callback=self.super_green_mark,
    #                               cbargs={'enable': enable, 'mark_mode': mark_mode})

    def generate_green_mark_area(self, mark_mode: GreenMarkType = GreenMarkType.GREEN_MAIN):
        result = None
        logger.info(mark_mode.name)
        match mark_mode:
            case GreenMarkType.GREEN_LEFT1:
                result = self.C_GREEN_LEFT_1
                logger.info("Green left 1")
            case GreenMarkType.GREEN_LEFT2:
                result = self.C_GREEN_LEFT_2
                logger.info("Green left 2")
            case GreenMarkType.GREEN_LEFT3:
                result = self.C_GREEN_LEFT_3
                logger.info("Green left 3")
            case GreenMarkType.GREEN_LEFT4:
                result = self.C_GREEN_LEFT_4
                logger.info("Green left 4")
            case GreenMarkType.GREEN_LEFT5:
                result = self.C_GREEN_LEFT_5
                logger.info("Green left 5")
            case GreenMarkType.GREEN_MAIN:
                result = self.C_GREEN_MAIN
                logger.info("Green main")
        return result

    def detect_name_position(self, img, names: str) -> list[int]:
        def similarity(txt1, txt2):
            txtset1 = set(txt1)
            txtset2 = set(txt2)
            intersection = txtset1.intersection(txtset2)
            union = txtset1.union(txtset2)
            return len(intersection) / len(union)

        name_list = names.split(',')
        for name in name_list:
            # 此处为了获取到OCR模型，随机选择一个了RuleOcr对象，可以使用任意的RuleOcr对象
            res_list = self.O_EXP_50.model.detect_and_ocr(img, 0.7)
            # 增加日志输出，方便纠错
            output = [item.ocr_text for item in res_list]
            logger.info(f"detect res_list:{output}")
            res = [item for item in res_list if similarity(item.ocr_text, name) > 0.5]
            res = sorted(res, key=lambda x: x.score)
            if len(res) <= 0:
                continue
            box = res[0].box
            logger.info(f"detect{res[0].ocr_text} with name:{name} in {box}")
            # 经实验，点击式神名称位置，可能点击不到，故此做一个修正
            offset = [5, 30, -10, 0]
            # x,y,w,h
            return [box[0, 0] + offset[0], box[0, 1] + offset[1], box[2, 0] - box[0, 0] + offset[2],
                    box[2, 1] - box[0, 1] + offset[3]]
        return None

    def calc_green_mark_locate_area(self, roi, margin=None):
        """
        @param roi: 根据名字OCR得出的ROI,格式为x,y,w,h
        @type roi: list[int]
        @param margin: 扩展大小，格式为top,right,bottom,left,同CSS margin
        @type margin:
        @return:
        @rtype:

        """
        if roi is None:
            return [0, 0, 1280, 720]
        result = [0, 0, 0, 0]
        if margin is None:
            margin = [160, 40, 20, 80]
        result[0] = x if (x := roi[0] - margin[3]) > 0 else 0
        result[1] = y if (y := roi[1] - margin[0]) > 0 else 0
        result[2] = w if (w := roi[2] + margin[1] + margin[3]) + x <= 1280 else 1280 - x
        result[3] = h if (h := roi[3] + margin[0] + margin[2]) + y <= 720 else 720 - y
        return result

    def detect_green_mark(self, img=None, area=None):
        def init_green_marker_roi(roi):
            self.I_GREEN_MARKER.roi_back = roi
            self.I_GREEN_MARKER_LEFT_TOP.roi_back = roi
            self.I_GREEN_MARKER_BOTTOM.roi_back = roi

        # 初始化绿标相关变量的roi信息
        if area is not None:
            init_green_marker_roi(area)
        elif self._green_mark_detect_area is not None:
            init_green_marker_roi(self._green_mark_detect_area)
        else:
            init_green_marker_roi((0, 0, 1280, 720))

        if img is not None:
            self.device.image = img

        def detect_green_marker_base(image):
            hsv_image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
            lower_green = np.array([67, 115, 110])
            upper_green = np.array([80, 255, 232])
            mask = cv2.inRange(hsv_image, lower_green, upper_green)
            result = cv2.bitwise_and(image, image, mask=mask)
            # 伤害数字，御魂生效后弹出会遮挡绿标信息，目前的策略：尽量的延长检测到绿标的时间
            res = (self.I_GREEN_MARKER_LEFT_TOP.match(result)
                   or self.I_GREEN_MARKER_BOTTOM.match(result)
                   or self.I_GREEN_MARKER.match(result))
            return res

        if detect_green_marker_base(self.device.image):
            return True
        return False

    def green_mark_screenshot(self, callback=None):
        """
            替代原有screenshot
        @return:
        @rtype:
        """
        self.screenshot()
        # 若未初始化，直接返回，不检测绿标状态
        if self._state == GreenMarkState.NOT_INIT or self._state is None:
            return self.device.image

        # 检测式神名区域
        if self._green_mark_click_roi is None and (self._shikigami_name is not None and self._shikigami_name != ""):
            self._green_mark_click_roi = self.detect_name_position(self.device.image, self._shikigami_name)
            if self._green_mark_click_roi is not None:
                self._green_mark_detect_area = self.calc_green_mark_locate_area(self._green_mark_click_roi)

        # 如果检测到绿标，直接返回
        if self.detect_green_mark(self.device.image):
            self._disappear_count = 0
            self._disappear_timer.reset()
            if self._state != GreenMarkState.MARKED:
                logger.info("green mark appear")
                self._state = GreenMarkState.MARKED
            return self.device.image

        if self._state != GreenMarkState.DISAPPEARED:
            logger.info("green mark DISappear")
            self._state = GreenMarkState.DISAPPEARED
        self._disappear_count += 1
        self._disappear_timer.start()
        if self.need_green_mark():
            if self.green_mark_with_area(interval=self.GREEN_MARK_INTERVAL):
                self._disappear_timer.reset()
                self._disappear_count = 0
                if callback is not None:
                    callback()
        return self.device.image

    def need_green_mark(self):
        result = self._disappear_count > self.MAX_DISAPPEAR_COUNT
        if result:
            logger.info("MAX DISAPPEAR COUNT reached,Need Green Mark")
            return True
        result |= self._disappear_timer.reached()
        if result:
            logger.info("MAX DISAPPEAR TIME reached,Need Green Mark")
            return True
        return result

    def green_mark_with_area(self, area=None, interval=1.5):
        """
            点击区域尝试添加绿标，不保证添加成功
        @param area: 格式 x,y,w,h
        @type area:
        @return:
        @rtype:
        """
        if area is None:
            area = self._green_mark_click_roi
        if area is None:
            logger.warn("Green Mark with area None,give up")
            return False
        self.C_GREEN_MARK_AREA.roi_front = area
        if self.click(self.C_GREEN_MARK_AREA, interval=interval):
            # NOTE 防止式神死亡导致的连续点击，程序退出
            self.device.click_record_clear()
            logger.info(f"green mark with area:{area}")
            return True
        return False

    def set_shikigami_name(self, name):
        self._shikigami_name = name

    def start_green_mark(self):
        self._state = GreenMarkState.INITED
        self._disappear_timer.clear()
        self._disappear_count = 0

    def stop_green_mark(self):
        self._state = GreenMarkState.NOT_INIT

    def set_disappear_count(self, count):
        # 设置消失次数，用于（主动触发执行绿标）
        self._disappear_count = count


def change_green_mark(obj):
    obj.old_green_mark = obj.green_mark
    obj.green_mark = obj.ex_green_mark_3_retry


if __name__ == '__main__':
    # 读取图片,然后转换为HSV格式 ,使用cv2 matchtemplate 比较
    import cv2
    import numpy as np


    def detect_green_marker_with_template(image_path, template_path):
        # 读取图片
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Failed to read image from {image_path}")
            return None

        # 读取模板图片
        template = cv2.imread(template_path)
        if template is None:
            logger.error(f"Failed to read template from {template_path}")
            return None

        # 转换为HSV格式
        image = cv2.cvtColor(image, cv2.COLOR_BGR2HLS)
        template = cv2.cvtColor(template, cv2.COLOR_BGR2HLS)
        #
        # image_h, image_s, image_v = cv2.split(image)
        # template_h, template_s, template_v = cv2.split(template)
        # image_s_norm = cv2.normalize(image_s, None, 0, 255, cv2.NORM_MINMAX)
        # image_v_norm = cv2.normalize(image_v, None, 0, 255, cv2.NORM_MINMAX)
        # template_s_norm = cv2.normalize(template_s, None, 0, 255, cv2.NORM_MINMAX)
        # template_v_norm = cv2.normalize(template_v, None, 0, 255, cv2.NORM_MINMAX)

        # clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        # image = clahe.apply(image_v)
        # template = clahe.apply(template_v)

        # 合并增强后的 HSV 通道
        # image_enhanced_hsv = cv2.merge([image_h, image_s, image_v])
        # template_enhanced_hsv = cv2.merge([template_h, template_s, template_v])

        # 合并归一化后的 HSV 通道
        # image = cv2.merge([image_h, image_s_norm, image_v_norm])
        # template = cv2.merge([template_h, template_s_norm, template_v_norm])

        # 使用matchTemplate进行比较
        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # 获取匹配结果的位置和相似度
        top_left = max_loc
        h, w = template.shape[:2]
        bottom_right = (top_left[0] + w, top_left[1] + h)

        # 绘制矩形框标记匹配区域（可选）
        cv2.rectangle(image, top_left, bottom_right, (0, 255, 0), 2)

        # 返回匹配结果
        return {
            "position": top_left,
            "similarity": max_val,
            "image": image
        }


    # 示例调用
    result = detect_green_marker_with_template("E:\\111.png", "E:\\same.png")
    if result:
        logger.info(f"Match found at position: {result['position']} with similarity: {result['similarity']}")
    else:
        logger.info("No match found.")

    result = detect_green_marker_with_template("E:\\111.png", "E:\\diff.png")
    if result:
        logger.info(f"Match found at position: {result['position']} with similarity: {result['similarity']}")
    else:
        logger.info("No match found.")

    result = detect_green_marker_with_template("E:\\222.png", "E:\\gb_prepare_highlight.png")
    if result:
        logger.info(f"Match found at position: {result['position']} with similarity: {result['similarity']}")
    else:
        logger.info("No match found.")

    result = detect_green_marker_with_template("E:\\222.png", "E:\\gb_prepare_dark.png")
    if result:
        logger.info(f"Match found at position: {result['position']} with similarity: {result['similarity']}")
    else:
        logger.info("No match found.")
