# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2
import numpy as np

from numpy import float32, int32, uint8, fromfile
from pathlib import Path

from module.atom.RuleImageMallResourceMixin import RuleImageMallResourceMixin
from module.base.decorator import cached_property
from module.logger import logger
from module.base.utils import is_approx_rectangle
from module.base.utils.utils import random_normal_distribution_int

# 模板匹配容差：把搜索区域（roi_back）四边各外扩该像素数，用于吸收非原生渲染
# 环境相对模板截图环境的整体相位差（桌面客户端受 DPI 缩放重采样，约 1px）。
# 仓库里约 1/3 的模板 roi_back 与模板等宽，此时 matchTemplate 结果只剩 1 列、
# 横向一格都平移不了，1px 相位差就足以把「元素存在」判成「不存在」。
# 桌面模式由 Device 置为 2，模拟器保持 0、行为逐位不变。
ROI_MATCH_PAD = 0
DESKTOP_ROI_MATCH_PAD = 2


def set_roi_match_padding(pad: int) -> None:
    """设置模板匹配的 roi_back 外扩容差（像素，四边同值）。0 表示不启用。"""
    global ROI_MATCH_PAD
    ROI_MATCH_PAD = max(0, int(pad))


class RuleImage(RuleImageMallResourceMixin):
    debug_mode: bool = False

    def __init__(self, roi_front: tuple, roi_back: tuple, method: str, threshold: float, file: str) -> None:
        """
        初始化
        :param roi_front: 前置roi
        :param roi_back: 后置roi 用于匹配的区域
        :param method: 匹配方法 "Template matching" / "Masked template matching" / "Multi-scale template matching" / "Sift Flann"
        :param threshold: 阈值  0.8
        :param file: 相对路径, 带后缀
        """
        self._match_init = False  # 这个是给后面的 等待图片稳定
        self._image = None  # 这个是匹配的目标
        self._kp = None  #
        self._des = None
        self._mask_loaded = False  # 掩码懒加载标记: False=未加载, 加载后看 _mask
        self._mask = None  # 掩码图, None 表示无掩码(回退普通匹配)
        self.last_score = -1.0  # 最近一次匹配的真实分数, -1 表示本次未产生分数
        self.last_scale = None  # 最近一次多尺度匹配命中的缩放倍数, 仅 Multi-scale 方法写入
        self.method = method

        self.roi_front: list = list(roi_front)
        self.roi_back = roi_back
        self.threshold = threshold
        self.file = file



    @cached_property
    def name(self) -> str:
        """

        :return:
        """
        return Path(self.file).stem.upper()

    def __str__(self):
        return self.name

    __repr__ = __str__

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self.name)

    def __bool__(self):
        return True



    def load_image(self) -> None:
        """
        加载图片
        :return:
        """
        if self._image is not None:
            return
        img = cv2.imdecode(fromfile(self.file, dtype=uint8), -1)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self._image = img

        height, width, channels = self._image.shape
        if height != self.roi_front[3] or width != self.roi_front[2]:
            self.roi_front[2] = width
            self.roi_front[3] = height
            logger.debug(f"{self.name} roi_front size changed to {width}x{height}")

    def load_kp_des(self) -> None:
        if self._kp is not None and self._des is not None:
            return
        self._kp, self._des = self.sift.detectAndCompute(self.image, None)


    @property
    def image(self):
        """
        获取图片
        :return:
        """
        if self._image is None:
            self.load_image()
        return self._image

    @cached_property
    def is_template_match(self) -> bool:
        """
        是否是模板匹配
        :return:
        """
        return self.method == "Template matching"

    @cached_property
    def is_masked_template_match(self) -> bool:
        """
        是否是掩码模板匹配，掩码取自同目录下 `xxx_mask.png`
        :return:
        """
        return self.method == "Masked template matching"

    @cached_property
    def is_multi_scale_template_match(self) -> bool:
        return self.method == "Multi-scale template matching"

    @cached_property
    def is_sift_flann(self) -> bool:
        return self.method == "Sift Flann"

    @cached_property
    def sift(self):
        return cv2.SIFT_create()

    @cached_property
    def kp(self):
        if self._kp is None:
            self.load_kp_des()
        return self._kp

    @cached_property
    def des(self):
        if self._des is None:
            self.load_kp_des()
        return self._des

    @staticmethod
    def _pad_roi(roi) -> tuple:
        """
        把 ROI 四边各外扩 ROI_MATCH_PAD 像素，返回 (x0, y0, w, h)。

        左上侧必须夹到 0：numpy 对负索引按「倒数」语义取值，会把裁剪位置算错，
        并连带把回算出的 roi_front 算偏；右/下侧越界由切片自然截断。
        返回的 x0/y0 是外扩后的原点，命中回算必须以它做基准。
        """
        x, y, w, h = [int(v) for v in roi]
        pad = ROI_MATCH_PAD
        if pad <= 0:
            return x, y, w, h
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        return x0, y0, x + w + pad - x0, y + h + pad - y0

    @property
    def mask(self):
        """
        掩码图，取模板同目录下 `xxx_mask.png`（`xxx.png` -> `xxx_mask.png`）。
        语义为「非零参与匹配，零忽略」。文件缺失、读取失败或尺寸与模板不一致时
        返回 None，由调用方回退到普通匹配，避免一张画错尺寸的掩码直接让规则报错。
        :return:
        """
        if not self._mask_loaded:
            self._mask_loaded = True
            path = Path(self.file)
            mask_path = path.with_name(f"{path.stem}_mask{path.suffix}")
            try:
                mask = cv2.imdecode(fromfile(str(mask_path), dtype=uint8), cv2.IMREAD_GRAYSCALE)
            except OSError:
                mask = None
            if mask is None:
                logger.debug(f"{self.name} template mask unavailable, fallback to plain matching: {mask_path}")
            elif mask.shape[:2] != self.image.shape[:2]:
                logger.error(
                    f"{self.name} template mask size mismatch "
                    f"{mask.shape[:2]} != {self.image.shape[:2]}, fallback to plain matching"
                )
            else:
                self._mask = mask
        return self._mask

    @staticmethod
    def _template_is_degenerate(template: np.ndarray, mask: np.ndarray | None = None) -> bool:
        """
        判断模板在参与匹配的区域内是否逐通道恒为常量。

        CCOEFF_NORMED 归一化时分母来自各通道的方差，参与区域内所有通道都完全没有起伏时，
        分母才是 0，OpenCV 会走特判：无掩码时整张结果矩阵被填成 1.0（恒假阳性，且落点固定
        在 roi_back 左上角），带掩码时整张变成 0/0 的 nan。两种都让这条规则失去意义，
        这里提前拦掉，而不是把异常数值当成命中。
        """
        if template is None or template.size == 0:
            return True
        region = template if mask is None else template[mask > 0]
        if region.size == 0:
            return True
        # 掩码取值后是 `(N, C)`、整体模板是 `(H, W, C)`、灰度图是 `(H, W)` 或 `(N,)`，
        # 通道数只认模板本身，再统一摊平成 `(N, C)` 逐通道判断。
        channels = 1 if template.ndim == 2 else template.shape[-1]
        samples = region.reshape(-1, channels)
        return all(float(samples[:, channel].std()) == 0.0 for channel in range(channels))

    @staticmethod
    def _sanitize_match_result(result: np.ndarray) -> np.ndarray:
        """
        压掉匹配结果矩阵里的非有限值。

        源图窗口整块同色时 CCOEFF_NORMED 会算出 nan/inf：nan 会让
        `max_val > threshold` 恒为假而静默漏检，inf 则会越过阈值并把命中位置指到随机
        坐标（假阳性，点错位置）。这里统一替换为 -1.0，等价于「该位置判不匹配」。
        """
        if np.isfinite(result).all():
            return result
        logger.error("match result contains nan/inf (solid-color region), treated as not matched")
        return np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)

    def corp(self, image: np.array, roi: list = None) -> np.array:
        """
        截取图片
        :param image:
        :param roi
        :return:
        """
        x, y, w, h = self._pad_roi(self.roi_back if roi is None else roi)
        return image[y:y + h, x:x + w]

    def match(self, image: np.array, threshold: float = None) -> bool:
        """
        :param threshold:
        :param image:
        :return:
        """
        if threshold is None:
            threshold = self.threshold

        if self.is_multi_scale_template_match:
            return self.match_multi_scale(image, threshold, scale_range=(0.6, 1.2))

        if not (self.is_template_match or self.is_masked_template_match):
            return self.sift_match(image)
            # raise Exception(f"unknown method {self.method}")

        source = self.corp(image)
        mat = self.image

        if mat is None or mat.shape[0] == 0 or mat.shape[1] == 0:
            logger.error(f"Template image is invalid: {mat.shape}")
            return False  # 模板无效, 匹配失败
        if mat.shape[0] > source.shape[0] or mat.shape[1] > source.shape[1]:
            # 模板大于源图, 视为无效匹配(避免 matchTemplate 的异常行为)
            return False

        mask = self.mask if self.is_masked_template_match else None
        if self._template_is_degenerate(mat, mask):
            logger.error(f"{self.name} template is flat (no variance in matching area), treated as not matched")
            return False

        if mask is None:
            res = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED)
        else:
            res = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED, mask=mask)
        res = self._sanitize_match_result(res)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)  # 最小匹配度，最大匹配度，最小匹配度的坐标，最大匹配度的坐标
        self.last_score = float(max_val)
        if self.debug_mode:
            logger.attr(self.name, f'matching score {max_val:.5f}')

        if max_val > threshold:
            x0, y0, _, _ = self._pad_roi(self.roi_back)
            self.roi_front[0] = max_loc[0] + x0
            self.roi_front[1] = max_loc[1] + y0
            return True
        else:
            return False

    def match_multi_scale(self, image: np.array, threshold: float = None,
                          scales: list = None, scale_range: tuple = None) -> bool:
        """
        多尺度模板匹配，自动尝试多个缩放比例以适应图片大小的变化
        :param image: 原始截图
        :param threshold: 匹配阈值
        :param scales: 缩放比例列表
        :param scale_range: 缩放范围 (start, end, step)，例如 (0.8, 1.2, 0.1)，step 默认为 0.1
        :return: 匹配是否成功
        """
        if threshold is None:
            threshold = self.threshold

        # 如果指定了 scale_range，自动生成 scales 列表
        if scale_range is not None:
            start, end = scale_range[:2]
            step = scale_range[2] if len(scale_range) > 2 else 0.1
            scales = sorted(set(round(x, 1) for x in np.arange(start, end + step, step)))

        if scales is None:
            scales = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
        else:
            scales = sorted(set(round(x, 1) for x in scales))

        source = self.corp(image)
        mat = self.image

        if mat is None or mat.shape[0] == 0 or mat.shape[1] == 0:
            logger.error(f"Template image is invalid: {mat.shape}")
            return False
        if self._template_is_degenerate(mat):
            logger.error(f"{self.name} template is flat (no variance), treated as not matched")
            return False

        # 预计算模板尺寸
        mat_h, mat_w = mat.shape[:2]
        source_h, source_w = source.shape[:2]

        best_score = 0
        best_loc = None
        best_scale = 1.0
        best_shape = None  # 最佳得分对应的是哪一档缩放尺寸, 回写 roi_front 只能用它
        self.last_scale = None

        for scale in scales:
            scaled_w = int(mat_w * scale)
            scaled_h = int(mat_h * scale)

            # 跳过无效缩放
            if scaled_w < 10 or scaled_h < 10:
                continue
            # 缩放后仍大于源图则跳过该尺度(避免 matchTemplate 契约问题)
            if scaled_w > source_w or scaled_h > source_h:
                continue

            try:
                scaled_mat = cv2.resize(mat, (scaled_w, scaled_h))
                res = cv2.matchTemplate(source, scaled_mat, cv2.TM_CCOEFF_NORMED)
                res = self._sanitize_match_result(res)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                if max_val > best_score:
                    best_score = max_val
                    best_loc = max_loc
                    best_scale = scale
                    best_shape = (scaled_w, scaled_h)
            except Exception as e:
                continue

        if self.debug_mode:
            logger.attr(self.name, f'best scale: {best_scale:.2f}, best score: {best_score:.5f}')
        self.last_score = float(best_score)
        if best_loc is not None:
            self.last_scale = float(best_scale)

        if best_score > threshold and best_loc is not None and best_shape is not None:
            x0, y0, _, _ = self._pad_roi(self.roi_back)
            self.roi_front[0] = best_loc[0] + x0
            self.roi_front[1] = best_loc[1] + y0
            self.roi_front[2] = best_shape[0]
            self.roi_front[3] = best_shape[1]
            return True
        else:
            return False

    def match_all(self, image: np.array, threshold: float = None, roi: list = None) -> list[tuple]:
        """
        区别于match，这个是返回所有的匹配结果
        :param roi:
        :param image:
        :param threshold:
        :return:
        """
        if roi is not None:
            self.roi_back = roi
        if threshold is None:
            threshold = self.threshold
        if not (self.is_template_match or self.is_masked_template_match):
            raise Exception(f"unknown method {self.method}")
        source = self.corp(image)
        mat = self.image
        mask = self.mask if self.is_masked_template_match else None
        if self._template_is_degenerate(mat, mask):
            logger.error(f"{self.name} template is flat (no variance in matching area), treated as not matched")
            return []
        if mask is None:
            results = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED)
        else:
            results = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED, mask=mask)
        results = self._sanitize_match_result(results)
        if results.size:
            self.last_score = float(results.max())
        locations = np.where(results >= threshold)
        matches = []
        x0, y0, _, _ = self._pad_roi(self.roi_back)
        for pt in zip(*locations[::-1]):  # (x, y) coordinates
            score = results[pt[1], pt[0]]
            # 得分, x, y, w, h
            x = x0 + pt[0]
            y = y0 + pt[1]
            matches.append((score, x, y, mat.shape[1], mat.shape[0]))
        return matches

    def match_all_any(self, image: np.array, threshold: float = None, roi: list = None, nms_threshold: float = 0.3) -> list[tuple]:
        """
        区别于match，这个是返回所有的匹配结果，去除冗余匹配项（例如：多个框选区域重叠的情况）时使用。
        :param roi:
        :param image:
        :param threshold:
        :return:
        """
        if roi is not None:
            self.roi_back = roi
        if threshold is None:
            threshold = self.threshold
        if not (self.is_template_match or self.is_masked_template_match):
            raise Exception(f"unknown method {self.method}")
        source = self.corp(image)
        mat = self.image
        mask = self.mask if self.is_masked_template_match else None
        if self._template_is_degenerate(mat, mask):
            logger.error(f"{self.name} template is flat (no variance in matching area), treated as not matched")
            return []
        if mask is None:
            results = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED)
        else:
            results = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED, mask=mask)
        results = self._sanitize_match_result(results)
        if results.size:
            self.last_score = float(results.max())
        locations = np.where(results >= threshold)
        matches = []
        x0, y0, _, _ = self._pad_roi(self.roi_back)
        for pt in zip(*locations[::-1]):  # (x, y) coordinates
            score = results[pt[1], pt[0]]
            # 得分, x, y, w, h
            x = x0 + pt[0]
            y = y0 + pt[1]
            matches.append((score, x, y, mat.shape[1], mat.shape[0]))
        if len(matches) > 0:
            scores = np.array([m[0] for m in matches])
            boxes = np.array([[m[1], m[2], m[3], m[4]] for m in matches])
            # 使用OpenCV的NMSBoxes
            indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), score_threshold=threshold, nms_threshold=nms_threshold)
            filtered_matches = [matches[i] for i in indices]
            return filtered_matches
        return matches

    def coord(self) -> tuple:
        """
        获取roi_front的随机的点击的坐标
        :return:
        """
        x, y, w, h = self.roi_front
        return x + random_normal_distribution_int(0, w), y + random_normal_distribution_int(0, h)

    def coord_more(self) -> tuple:
        """
         获取roi_back的随机的点击的坐标
        :return:
        """
        x, y, w, h = self.roi_back
        return x + random_normal_distribution_int(0, w), y + random_normal_distribution_int(0, h)

    def front_center(self) -> tuple:
        """
        获取roi_front的中心坐标
        :return:
        """
        x, y, w, h = self.roi_front
        return int(x + w//2), int(y + h//2)

    def test_match(self, image: np.array):
        self.debug_mode = True
        if self.is_template_match or self.is_masked_template_match or self.is_multi_scale_template_match:
            return self.match(image)
        if self.is_sift_flann:
            return self.sift_match(image, show=True)

    def sift_match(self, image: np.array, show=False) -> bool:
        """
        特征匹配，同样会修改 roi_front
        :param image: 是游戏的截图，就是转通道后的截图
        :param show: 测试用的
        :return:
        """
        source = self.corp(image)
        kp, des = self.sift.detectAndCompute(source, None)
        # 参数1：index_params
        #    对于SIFT和SURF，可以传入参数index_params=dict(algorithm=FLANN_INDEX_KDTREE, trees=5)。
        #    对于ORB，可以传入参数index_params=dict(algorithm=FLANN_INDEX_LSH, table_number=6, key_size=12）。
        index_params = dict(algorithm=1, trees=5)
        # 参数2：search_params 指定递归遍历的次数，值越高结果越准确，但是消耗的时间也越多。
        search_params = dict(checks=50)
        # 根据设置的参数创建特征匹配器 指定匹配的算法和kd树的层数,指定返回的个数
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        # 利用创建好的特征匹配器利用k近邻算法来用模板的特征描述符去匹配图像的特征描述符，k指的是返回前k个最匹配的特征区域
        # 返回的是最匹配的两个特征点的信息，返回的类型是一个列表，列表元素的类型是Dmatch数据类型，具体是什么我也不知道
        # 第一个参数是小图的des, 第二个参数是大图的des
        matches = flann.knnMatch(self.des, des, k=2)

        good = []
        result = True
        for i, (m, n) in enumerate(matches):
            # 设定阈值, 距离小于对方的距离的0.7倍我们认为是好的匹配点.
            if m.distance < 0.6 * n.distance:
                good.append(m)
        if len(good) >= 10:
            src_pts = float32([self.kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = float32([kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

            # 计算透视变换矩阵m， 要求点的数量>=4
            m, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            # 创建一个包含模板图像四个角坐标的数组
            w, h = self.roi_front[2], self.roi_front[3]
            pts = float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
            if m is None:
                result = False
            else:
                dst = int32(cv2.perspectiveTransform(pts, m))
                x0, y0, _, _ = self._pad_roi(self.roi_back)
                self.roi_front[0] = dst[0, 0, 0] + x0
                self.roi_front[1] = dst[0, 0, 1] + y0
                if show:
                    cv2.polylines(source, [dst], isClosed=True, color=(0, 0, 255), thickness=2)
                if not is_approx_rectangle(np.array([pos[0] for pos in dst])):
                    result = False
        else:
            result = False

        # https://blog.csdn.net/cungudafa/article/details/105399278
        # https://blog.csdn.net/qq_45832961/article/details/122776322
        if show:
            # 准备一个空的掩膜来绘制好的匹配
            mask_matches = [[0, 0] for i in range(len(matches))]
            # 向掩膜中添加数据
            for i, (m, n) in enumerate(matches):
                if m.distance < 0.6 * n.distance:  # 理论上0.7最好
                    mask_matches[i] = [1, 0]
            img_matches = cv2.drawMatchesKnn(self.image, self.kp, source, kp, matches, None,
                                             matchColor=(0, 255, 0), singlePointColor=(255, 0, 0),
                                             matchesMask=mask_matches, flags=0)
            cv2.imshow(f'Sift Flann: {self.name}', img_matches)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        return result

    def match_mean_color(self, image, color: tuple, bias=10) -> bool:
        """

        :param image:
        :param color:  rgb
        :param bias:
        :return:
        """
        image = self.corp(image)
        average_color = cv2.mean(image)
        if self.debug_mode:
            logger.info(f'{self.name} average_color: {average_color}')
        for i in range(3):
            if abs(average_color[i] - color[i]) > bias:
                return False
        return True

    def match_brightness(
            self, image: np.array,
            threshold: float = 0.9,
            roi: list = None,
            gray: bool = False) -> bool:
        source = self.corp(image, roi) if roi is not None else self.corp(image)
        template = self.image

        if len(source.shape) != 3:
            raise Exception(f'{self.name} source image must be 3-channel RGB, got shape={source.shape}')
        source_gray = cv2.cvtColor(source, cv2.COLOR_RGB2GRAY)
        source_hsv = cv2.cvtColor(source, cv2.COLOR_RGB2HSV)

        if len(template.shape) != 3:
            raise Exception(f'{self.name} template image must be 3-channel RGB, got shape={template.shape}')
        template_gray = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)
        template_hsv = cv2.cvtColor(template, cv2.COLOR_RGB2HSV)

        source_value = float(source_gray.mean()) if gray else float(source_hsv[:, :, 2].mean())
        template_value = float(template_gray.mean()) if gray else float(template_hsv[:, :, 2].mean())
        score = 1.0 - abs(source_value - template_value) / 255.0
        score = max(0.0, min(1.0, score))

        if self.debug_mode:
            logger.attr(self.name, f'brightness similarity {score:.5f}')
            logger.info(f'Template value: {template_value}, Source value: {source_value}')
        return score >= threshold

    def match_saturation(self, image: np.array, threshold: float = 0.9, roi: list = None) -> bool:
        source = self.corp(image, roi) if roi is not None else self.corp(image)
        template = self.image

        if len(source.shape) != 3:
            raise Exception(f'{self.name} source image must be 3-channel RGB, got shape={source.shape}')
        source_hsv = cv2.cvtColor(source, cv2.COLOR_RGB2HSV)

        if len(template.shape) != 3:
            raise Exception(f'{self.name} template image must be 3-channel RGB, got shape={template.shape}')
        template_hsv = cv2.cvtColor(template, cv2.COLOR_RGB2HSV)

        source_value = float(source_hsv[:, :, 1].mean())
        template_value = float(template_hsv[:, :, 1].mean())
        score = 1.0 - abs(source_value - template_value) / 255.0
        score = max(0.0, min(1.0, score))

        if self.debug_mode:
            logger.attr(self.name, f'saturation similarity {score:.5f}')
            logger.info(f'Template value: {template_value}, Source value: {source_value}')
        return score >= threshold

if __name__ == "__main__":
    from dev_tools.assets_test import detect_image

    IMAGE_FILE = './log/test/QQ截图20240223151924.png'
    from tasks.Restart.assets import RestartAssets
    jade = RestartAssets.I_HARVEST_JADE
    jade.method = 'Sift Flann'
    sign = RestartAssets.I_HARVEST_SIGN
    sign.method = 'Sift Flann'
    print(jade.roi_front)

    detect_image(IMAGE_FILE, jade)
    detect_image(IMAGE_FILE, sign)
    print(jade.roi_front)
