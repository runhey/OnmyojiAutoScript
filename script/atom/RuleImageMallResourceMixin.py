# module/atom/image/image_mall_resource.py

from module.logger import logger
from module.atom.ocr import RuleOcr


class RuleImageMallResourceMixin:
    """
    RuleImage 的 mall_resource 能力扩展
    """

    # mall_resource 专用偏移参数
    MALL_RESOURCE_X_OFFSET = 40
    MALL_RESOURCE_RIGHT_EXTEND = 70

    def match_and_get_roi(self, image, threshold=None):
        """
        - match 成功 → 返回 (x, y, w, h)
        - match 失败 / 异常 → 返回 None
        """
        try:
            ok = self.match(image, threshold)
        except Exception as e:
            logger.error(f"match exception: {e}")
            return None

        if not ok:
            return None

        try:
            mat = self.image
            if mat is None or mat.shape[0] == 0 or mat.shape[1] == 0:
                return None

            h, w = mat.shape[:2]
            x = int(self.roi_front[0])
            y = int(self.roi_front[1])

            return (x, y, int(w), int(h))
        except Exception:
            return None

    def get_mall_resource_text_roi(self, image, threshold=None):
        """
        mall_resource 专用：
        - 定位 icon
        - 推导文本 OCR ROI

        return: roi or None
        """
        try:
            icon_roi = self.match_and_get_roi(image, threshold)
            if icon_roi is None:
                # 回退 roi_front
                ix, iy, iw, ih = self.roi_front
            else:
                ix, iy, iw, ih = icon_roi

            x = int(ix) + self.MALL_RESOURCE_X_OFFSET
            y = int(iy)
            w = int(iw) + self.MALL_RESOURCE_RIGHT_EXTEND
            h = int(ih)

            return (x, y, w, h)
        except Exception:
            return None

    def build_mall_resource_ocr(self, image, threshold=None, name="mall_resource"):
        """
        mall_resource 专用快捷方法：
        - 定位 icon
        - 推导 OCR ROI
        - 构造 RuleOcr

        return: RuleOcr | None
        """
        try:
            roi = self.get_mall_resource_text_roi(image, threshold)
            if roi is None:
                return None

            return RuleOcr(
                roi=roi,
                area=roi,
                mode="Quantity",
                method="Default",
                keyword="",
                name=name
            )
        except Exception:
            return None
