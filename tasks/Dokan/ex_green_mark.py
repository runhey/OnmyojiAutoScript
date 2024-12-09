import threading
import cv2
import numpy as np

from module.base.timer import Timer
from module.logger import logger
from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType
from tasks.Component.GeneralBattle.general_battle import GeneralBattle


def green_marker_detector(func):
    def wrapper(self, *args, **kwargs):
        event = threading.Event()

        def detect_green_marker(image):
            hsv_image = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
            lower_green = np.array([67, 115, 110])
            upper_green = np.array([80, 255, 232])
            mask = cv2.inRange(hsv_image, lower_green, upper_green)
            result = cv2.bitwise_and(image, image, mask=mask)
            res = self.I_GREEN_MARKER.match(result)
            return res

        def emit_exists():
            logger.info("Green marker detected!")
            unpack_screenshot()
            event.set()

        def screenshot_and_detect():
            self.just_screenshot()
            exists = detect_green_marker(self.device.image)
            if exists:
                emit_exists()
            return self.device.image

        def pack_screenshot():
            self.just_screenshot = self.screenshot
            self.screenshot = screenshot_and_detect

        def unpack_screenshot():
            self.screenshot = self.just_screenshot

        def thread_run(self, detect_time=3, cb=None, cbargs=None):
            logger.info("detect thread running...")
            t = Timer(detect_time)
            t.start()
            while event.wait(detect_time):
                logger.info("detect thread quit")
                return
            unpack_screenshot()
            if cb:
                logger.info(f"didn't detect green mark ,start running callback with arg:{cbargs}")
                try:
                    cb(**cbargs)
                except Exception as e:
                    logger.error(f"callback error:{e}")

        # wrapper
        callback = kwargs.get('callback', None)
        cbargs = kwargs.get('cbargs', None)
        detect_time = kwargs.get('detect_time', 3.0)

        if callback:
            logger.info("Green marker detector running...")
            pack_screenshot()
        # green mark 函数的参数列表
        kwarg_key = ['enable', 'mark_mode']
        func_kwargs = {key: kwargs[key] for key in kwarg_key if key in kwargs}
        if not event.is_set():
            func(self, *args, **func_kwargs)

        if callback:
            thread = threading.Thread(target=thread_run, args=(self, detect_time, callback, cbargs), daemon=True)
            thread.start()
        return

    return wrapper


class ExtendGreenMark(GeneralBattle):

    def __init__(self, config, device):
        super().__init__(config, device)
        self.super_green_mark = self.green_mark

    @green_marker_detector
    def ex_green_mark(self, enable=True, mark_mode=GreenMarkType.GREEN_MAIN):
        if not enable:
            return
        return self.super_green_mark(enable=enable, mark_mode=mark_mode)

    def ex_green_mark_3_retry(self, enable=True, mark_mode=GreenMarkType.GREEN_MAIN):
        if not enable:
            return
        return self.ex_green_mark(enable=enable, mark_mode=mark_mode, detect_time=3, callback=self.super_green_mark,
                                  cbargs={'enable': enable, 'mark_mode': mark_mode})

    def green_mark_without_check(self, enable=True, mark_mode=GreenMarkType.GREEN_MAIN):
        if not enable:
            return
        logger.info("Green is enable")
        x, y = None, None
        match mark_mode:
            case GreenMarkType.GREEN_LEFT1:
                x, y = self.C_GREEN_LEFT_1.coord()
                logger.info("Green left 1")
            case GreenMarkType.GREEN_LEFT2:
                x, y = self.C_GREEN_LEFT_2.coord()
                logger.info("Green left 2")
            case GreenMarkType.GREEN_LEFT3:
                x, y = self.C_GREEN_LEFT_3.coord()
                logger.info("Green left 3")
            case GreenMarkType.GREEN_LEFT4:
                x, y = self.C_GREEN_LEFT_4.coord()
                logger.info("Green left 4")
            case GreenMarkType.GREEN_LEFT5:
                x, y = self.C_GREEN_LEFT_5.coord()
                logger.info("Green left 5")
            case GreenMarkType.GREEN_MAIN:
                x, y = self.C_GREEN_MAIN.coord()
                logger.info("Green main")

        # 点击绿标
        self.device.click(x, y)

    def custom_callback(self, enable=True, mark_mode=GreenMarkType.GREEN_MAIN):

        return self.green_mark_without_check(enable, mark_mode)


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
