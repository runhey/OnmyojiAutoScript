# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2

from numpy import float32, int32, uint8, fromfile
from PySide6.QtCore import QUrl, Property
from PySide6.QtGui import QImage, QPainter
from PySide6.QtQuick import QQuickPaintedItem
from PySide6.QtCore import QObject, Slot, Signal

from module.logger import logger


class PaintImage(QQuickPaintedItem):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = QImage()

    def paint(self, painter: QPainter):
        if self._image.isNull():
            logger.error("image is null")
            return
        painter.drawImage(self.boundingRect(), self._image)

    def image(self):
        return self._image

    def set_image(self, image: QImage):
        if self._image == image:
            return None
        self._image = image
        # 更新会触发paint事件
        self.update()

    @Slot(str)
    def set_local(self, image_name: str):
        if not image_name.startswith("file:///"):
            logger.error("image path must start with file:///")
            return None
        image_name = image_name.lstrip("file:///")


        if self._image.load(image_name):
            logger.info("load image success")
            self.update()
        else:
            logger.error("load image failed")
            return None

    image = Property(QImage, fget=image, fset=set_image, notify=logger.info)

    @Slot(str, str)
    def save_target_image(self, roi: str, file: str) -> None:
        """
        保存目标图片
        :param file: 保存的文件名
        :param roi: 截图的范围 文本如"0,0,100,100"
        :return:
        """
        if not roi:
            return
        if not isinstance(roi, str):
            logger.error("roi must be str")
        if not file:
            return
        if not isinstance(file, str):
            logger.error("file must be str")
            return
        x, y, width, height = map(int, roi.split(','))
        roi_image = self._image.copy(x, y, width, height)
        roi_image.save(file)
        logger.info(f"save target image {file}success")
