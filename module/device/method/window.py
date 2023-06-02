# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2
from numpy import frombuffer, uint8, array, random
import numpy as np
import time

from math import dist
from cached_property import cached_property
from win32gui import (GetWindowText, EnumWindows, FindWindow, FindWindowEx,
                      IsWindow, GetWindowRect, GetWindowDC, DeleteObject,
                      SetForegroundWindow, IsWindowVisible, GetDC, GetParent,
                      EnumChildWindows)
from win32con import (SRCCOPY, DESKTOPHORZRES, DESKTOPVERTRES, WM_LBUTTONUP,
                      WM_LBUTTONDOWN, WM_ACTIVATE, WA_ACTIVE, MK_LBUTTON,
                      WM_NCHITTEST, WM_SETCURSOR, HTCLIENT, WM_MOUSEMOVE)
from win32ui import CreateDCFromHandle, CreateBitmap
from win32api import GetSystemMetrics, SendMessage, MAKELONG, PostMessage
from win32con import SRCCOPY

from module.base.cBezier import BezierTrajectory
from module.exception import RequestHumanTakeover, ScriptError
from module.base.decorator import Config
from module.base.timer import timer
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

    @cached_property
    def control_handle_list(self) -> list:
        """
        不同的模拟器需要的子句柄不同
        mumu模拟器的控制需要 根窗口和第一个子窗口
        雷电模拟器只需要TheRender窗口
        夜神模拟器
        :return:
        """
        result = []
        if self.emulator_family == "mumu_player_family":
            result.append(self.root_node.num)
            result.append(self.root_node.children[0].num)
            return result
        elif self.emulator_family == 'nox_player_family':
            result.append(self.root_node.num)
            try:
                result.append(self.root_node.children[1].num)
                result.append(self.root_node.children[1].children[1].num)
                result.append(self.root_node.children[1].children[1].children[0].num)
            except:
                result.append(self.root_node.children[2].num)
                result.append(self.root_node.children[2].children[1].num)
                result.append(self.root_node.children[2].children[1].children[0].num)
            return result
        elif self.emulator_family == 'ld_player_family':
            result.append(self.root_node.children[0].num)
            return result
        elif self.emulator_family == 'memu_player_family':
            pass
        elif self.emulator_family == 'bluestacks_family':
            pass

    def click_window_message(self, x: int, y: int):
        """

        :param x:
        :param y:
        :return:
        """
        # if x >= 1280:
        #     x = 1280
        # if x <= 0:
        #     x = 0
        # if y >= 720:
        #     y = 720
        # if y <= 0:
        #     y = 0
        # 我不知道为什么的使用的pywin32==306的版本会导致获取的图片的是(1024, 576)
        # 所有我在点击的时候会除以这个缩放比例
        x = int(x / self.window_scale_rate)
        y = int(y / self.window_scale_rate)
        logger.info(self.control_handle_list)
        emulator_type = len(self.control_handle_list)
        if emulator_type == 2:  # mumu模拟器
            SendMessage(self.control_handle_list[0], WM_LBUTTONDOWN, 0, MAKELONG(x, y))  # 模拟鼠标按下 先是父窗口 上面的框高度是57
            time.sleep((random.randint(100, 200)) / 1000.0)  # 点击弹起改为随机,时间100ms-200ms
            SendMessage(self.control_handle_list[1], WM_LBUTTONUP, 0, MAKELONG(x, y))  # 模拟鼠标弹起 后是子窗口
        elif emulator_type > 2:  # 夜神模拟器
            SendMessage(self.control_handle_list[0], WM_LBUTTONDOWN, 0, MAKELONG(x, y))  # 模拟鼠标按下 先是父窗口 上面的框高度是57
            SendMessage(self.control_handle_list[1], WM_LBUTTONDOWN, 0, MAKELONG(x, y))
            SendMessage(self.control_handle_list[2], WM_LBUTTONDOWN, 0, MAKELONG(x, y))
            SendMessage(self.control_handle_list[3], WM_LBUTTONDOWN, 0, MAKELONG(x, y))
            time.sleep((random.randint(100, 200)) / 1000.0)  # 点击弹起改为随机,时间100ms-200ms
            SendMessage(self.control_handle_list[3], WM_LBUTTONUP, 0, MAKELONG(x, y))  # 模拟鼠标弹起 后是子窗口
        elif emulator_type == 1:  # 雷电模拟器
            clickPos = MAKELONG(x, y)
            SendMessage(self.control_handle_list[0], WM_LBUTTONDOWN, 0, clickPos)  # 模拟鼠标按下
            time.sleep((random.randint(100, 200)) / 1000.0)  # 点击弹起改为随机,时间100ms-200ms
            SendMessage(self.control_handle_list[0], WM_LBUTTONUP, 0, clickPos)  # 模拟鼠标弹起

    def long_click_window_message(self, x: int, y: int, duration: float):
        """

        :param x:
        :param y:
        :param duration: 持续时间 单位秒
        :return:
        """
        # 我不知道为什么的使用的pywin32==306的版本会导致获取的图片的是(1024, 576)
        # 所有我在点击的时候会除以这个缩放比例
        x = int(x / self.window_scale_rate)
        y = int(y / self.window_scale_rate)
        logger.info(self.control_handle_list)
        emulator_type = len(self.control_handle_list)
        if emulator_type == 2:  # mumu模拟器
            SendMessage(self.control_handle_list[0], WM_LBUTTONDOWN, 0, MAKELONG(x, y))  # 模拟鼠标按下 先是父窗口 上面的框高度是57
            time.sleep(duration)  # 长按时间1000ms-1500ms
            SendMessage(self.control_handle_list[1], WM_LBUTTONUP, 0, MAKELONG(x, y))  # 模拟鼠标弹起 后是子窗口
        elif emulator_type > 2:  # 夜神模拟器
            SendMessage(self.control_handle_list[0], WM_LBUTTONDOWN, 0, MAKELONG(x, y))  # 模拟鼠标按下 先是父窗口 上面的框高度是57
            SendMessage(self.control_handle_list[1], WM_LBUTTONDOWN, 0, MAKELONG(x, y))
            SendMessage(self.control_handle_list[2], WM_LBUTTONDOWN, 0, MAKELONG(x, y))
            SendMessage(self.control_handle_list[3], WM_LBUTTONDOWN, 0, MAKELONG(x, y))
            time.sleep(duration)  # 长按时间1000ms-1500ms
            SendMessage(self.control_handle_list[3], WM_LBUTTONUP, 0, MAKELONG(x, y))  # 模拟鼠标弹起 后是子窗口
        elif emulator_type == 1:  # 雷电模拟器
            clickPos = MAKELONG(x, y)
            SendMessage(self.control_handle_list[0], WM_LBUTTONDOWN, 0, clickPos)  # 模拟鼠标按下
            time.sleep(duration)  # 长按时间1000ms-1500ms
            SendMessage(self.control_handle_list[0], WM_LBUTTONUP, 0, clickPos)  # 模拟鼠标弹起

    # @timer
    def swipe_window_message(self, startPos: list, endPos: list) -> None:
        """
        后台滑动
        :param startPos:
        :param endPos:
        :return:
        """
        # 生成的坐标点列表
        interval: int = 8  # 每次移动的间隔时间
        numberList: int = int(dist(startPos, endPos) / (1.5 * interval))  # 表示每毫秒移动1.5个像素点， 总的时间除以每个点10ms就得到总的点的个数
        le = random.randint(2, 4)  #
        deviation = random.randint(20, 40)  # 幅度
        _type: int = 3
        obbsType = random.random()  # 0.8的概率是先快中间慢后面快， 0.1概率是先快后慢， 0.1概率先慢后快
        if 0 < obbsType <= 0.8:
            _type = 3
        elif obbsType < 0.9:
            _type = 2
        else:
            _type = 1
        trace: list = BezierTrajectory.trackArray(start=startPos, end=endPos, numberList=numberList, le=le,
                                                  deviation=deviation, bias=0.5, type=_type, cbb=0, yhh=20)

        # 使用生成的点列表进行拖拽
        emulator_type = len(self.control_handle_list)
        if emulator_type == 1:  # 雷电模拟器
            handleNum = self.control_handle_list[0]
        elif emulator_type == 2:  # mumu模拟器
            handleNum = self.control_handle_list[1]
        elif emulator_type > 2:  # 夜神模拟器
            handleNum = self.control_handle_list[3]
        PostMessage(handleNum, WM_ACTIVATE, WA_ACTIVE, 0)  # 激活窗口
        # 先移动到第一个点
        tmpPos = MAKELONG(trace[0][0], trace[0][1])
        SendMessage(handleNum, WM_NCHITTEST, 0, tmpPos)
        SendMessage(handleNum, WM_SETCURSOR, handleNum, MAKELONG(HTCLIENT, WM_LBUTTONDOWN))
        PostMessage(handleNum, WM_LBUTTONDOWN, MK_LBUTTON, tmpPos)
        # 一点一点移动鼠标
        for pos in trace:
            tmpPos = MAKELONG(pos[0], pos[1])
            PostMessage(handleNum, WM_MOUSEMOVE, MK_LBUTTON, tmpPos)
            time.sleep((interval + random.randint(-2, 2)) / 1000.0)
        # 最后释放鼠标
        tmpPos = MAKELONG(trace[-1][0], trace[-1][1])
        PostMessage(handleNum, WM_LBUTTONUP, 0, tmpPos)

    def swipe_vector_window_message2(self, startPos: list, endPos: list) -> None:
        """
        后台滑动
        :param startPos:
        :param endPos:
        :return:
        """
        # 生成的坐标点列表
        interval: int = 8  # 每次移动的间隔时间
        numberList: int = int(dist(startPos, endPos) / (1.5 * interval))  # 表示每毫秒移动1.5个像素点， 总的时间除以每个点10ms就得到总的点的个数

        def generate_points(start_pos: list, end_pos: list, number: int) -> list:
            # 确定两点之间的步长
            step_x = (end_pos[0] - start_pos[0]) / (number + 1)
            step_y = (end_pos[1] - start_pos[1]) / (number + 1)
            # 生成中间点坐标列表
            points = []
            for i in range(number):
                x = start_pos[0] + step_x * (i + 1)
                y = start_pos[1] + step_y * (i + 1)
                points.append((x, y))
            # 添加起始点和最终点到列表中
            points.insert(0, tuple(start_pos))
            points.append(tuple(end_pos))
            return points

        trace: list = generate_points(start_pos=startPos, end_pos=endPos, number=numberList)

        # 使用生成的点列表进行拖拽
        emulator_type = len(self.control_handle_list)
        if emulator_type == 1:  # 雷电模拟器
            handleNum = self.control_handle_list[0]
        elif emulator_type == 2:  # mumu模拟器
            handleNum = self.control_handle_list[1]
        elif emulator_type > 2:  # 夜神模拟器
            handleNum = self.control_handle_list[3]
        PostMessage(handleNum, WM_ACTIVATE, WA_ACTIVE, 0)  # 激活窗口
        # 先移动到第一个点
        tmpPos = MAKELONG(trace[0][0], trace[0][1])
        SendMessage(handleNum, WM_NCHITTEST, 0, tmpPos)
        SendMessage(handleNum, WM_SETCURSOR, handleNum, MAKELONG(HTCLIENT, WM_LBUTTONDOWN))
        PostMessage(handleNum, WM_LBUTTONDOWN, MK_LBUTTON, tmpPos)
        # 一点一点移动鼠标
        for pos in trace:
            tmpPos = MAKELONG(pos[0], pos[1])
            PostMessage(handleNum, WM_MOUSEMOVE, MK_LBUTTON, tmpPos)
            time.sleep((interval + random.randint(-2, 2)) / 1000.0)
        # 最后释放鼠标
        tmpPos = MAKELONG(trace[-1][0], trace[-1][1])
        PostMessage(handleNum, WM_LBUTTONUP, 0, tmpPos)


if __name__ == "__main__":
    w = Window(config='oas1')
    # w.screenshot_window_background()
    # w.click_window_message(x=350, y=220)
    w.swipe_window_message(startPos=[200, 5], endPos=[300, 300])
