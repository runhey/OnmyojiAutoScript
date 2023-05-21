# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2
from numpy import frombuffer, uint8, array, random
import numpy as np
import time
from win32gui import (GetWindowText, EnumWindows, FindWindow, FindWindowEx,
                      IsWindow, GetWindowRect, GetWindowDC, DeleteObject,
                      SetForegroundWindow, IsWindowVisible, GetDC, GetParent,
                      EnumChildWindows)
from win32ui import CreateDCFromHandle, CreateBitmap
from win32con import SRCCOPY

from module.exception import RequestHumanTakeover, ScriptError
from module.logger import logger
from module.device.handle import Handle, window_scale_rate

class Window(Handle):

    def screenshot_window_background(self):
        """
        后台截屏
        :return:
        """
        win_size = self.screenshot_size
        scale_rate = window_scale_rate()
        widthScreen = int(win_size[0] * scale_rate)
        heightScreen = int(win_size[1] * scale_rate)
        # 返回句柄窗口的设备环境，覆盖整个窗口，包括非客户区，标题栏，菜单，边框
        hwndDc = GetWindowDC(self.screenshot_handle_num)
        # 创建设备描述表
        mfcDc = CreateDCFromHandle(hwndDc)
        # 创建内存设备描述表
        saveDc = mfcDc.CreateCompatibleDC()
        # 创建位图对象准备保存图片
        saveBitMap = CreateBitmap()
        # 为bitmap开辟存储空间
        saveBitMap.CreateCompatibleBitmap(mfcDc, widthScreen, heightScreen)
        # 将截图保存到saveBitMap中
        saveDc.SelectObject(saveBitMap)
        # 保存bitmap到内存设备描述表
        saveDc.BitBlt((0, 0), (widthScreen, heightScreen), mfcDc, (0, 0), SRCCOPY)

        # 保存图像
        signedIntsArray = saveBitMap.GetBitmapBits(True)
        imgSrceen = frombuffer(signedIntsArray, dtype='uint8')
        imgSrceen.shape = (heightScreen, widthScreen, 4)
        # imgSrceen = cv2.cvtColor(imgSrceen, cv2.COLOR_BGRA2GRAY)
        imgSrceen = cv2.resize(imgSrceen, (win_size[0], win_size[1]))

        # 测试显示截图图片
        cv2.namedWindow('imgSrceen')  # 命名窗口
        cv2.imshow("imgSrceen", imgSrceen)  # 显示
        cv2.waitKey(0)
        cv2.destroyAllWindows()

        # 内存释放
        DeleteObject(saveBitMap.GetHandle())
        saveDc.DeleteDC()
        mfcDc.DeleteDC()
        return imgSrceen


if __name__ == "__main__":
    w = Window(config='oas1')
    w.screenshot_window_background()