# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re

from cached_property import cached_property
from anytree import NodeMixin, RenderTree
from win32process import GetWindowThreadProcessId
from win32gui import (GetWindowText, EnumWindows, FindWindow, FindWindowEx,
                      IsWindow, GetWindowRect, GetWindowDC, DeleteObject,
                      SetForegroundWindow, IsWindowVisible, GetDC, GetParent,
                      EnumChildWindows)

from module.config.config import Config
from module.exception import RequestHumanTakeover, EmulatorNotRunningError
from module.logger import logger


def handle_title2num(title: str) -> int:
    """
    从标题到句柄号
    :param title:
    :return:  如果没有找到就是返回零
    """
    return FindWindow(None, title)


def handle_num2title(num: int) -> str:
    """
    通过句柄号返回窗口的标题，如果传入句柄号不合法则返回None
    :param num:
    :return:
    """
    return None if num is None or num == 0 or num == '' else GetWindowText(num)


def is_handle_valid(num: int) -> bool:
    """
    输入一个句柄号，如果还在返回True
    :param num:
    :return:
    """
    return IsWindow(num)

def handle_num2pid(num :int) -> int:
    """
    通过句柄号获取句柄进程id，如果句柄号非法则返回0
    :param num:
    :return:
    """
    return 0 if num is None or num == 0 or num == '' else GetWindowThreadProcessId(num)[1]


class WindowNode(NodeMixin):
    def __init__(self, name, num, parent=None):
        super().__init__()
        self.name = name
        self.num = num
        self.parent = parent


class Handle:
    emulator_list = ['MuMu',
                     '雷电',
                     '夜神',
                     '蓝叠',
                     '逍遥',
                     '模拟器']  # 最后一个我又不知道还有哪些模拟器
    emulator_handle = {
        # 夜神
        'nox_player': ['root_handle_title', 'Nox'],
        'nox_player_64': ['root_handle_title', 'Nox'],
        'nox_player_family':['root_handle_title', 'Nox'],
        # 雷电
        'ld_player': ['TheRender'],
        'ld_player_4': ['TheRender'],
        'ld_player_9': ['TheRender'],
        'ld_player_family': ['TheRender'],
        # 逍遥
        'memu_player': ['root_handle_title'],
        'memu_player_family': ['root_handle_title'],
        # mumu
        'mumu_player': ['root_handle_title', 'NemuPlayer'],
        'mumu_player_12': ['root_handle_title', 'MuMuPlayer'],
        'mumu_player_family': ['root_handle_title', 'MuMuPlayer'],
        # 蓝叠
        'bluestacks_5': ['root_handle_title'],
        'bluestacks_family': ['root_handle_title']
    }

    def __init__(self, config) -> None:
        """

        :param config:
        """
        logger.hr('Handle')
        if isinstance(config, str):
            self.config = Config(config, task=None)
        else:
            self.config = config

        # 获取根的句柄
        self.root_handle_title = ''
        self.root_handle_num = 0
        self.root_handle = self.config.get_arg('Script', 'Device', 'Handle')
        if self.root_handle == "auto":
            logger.info('handle is auto. oas will find window emulator')
            window_list = Handle.all_windows()
            self.root_handle_title = self.auto_handle_title(window_list)
            self.root_handle_num = handle_title2num(self.root_handle_title)
        elif isinstance(self.root_handle, int):
            logger.info('handle is handle num. oas use it as root handle num')
            if is_handle_valid(self.root_handle):
                logger.info(f'handle number {self.root_handle} is valid')
                self.root_handle_title = handle_num2title(self.root_handle)
                self.root_handle_num = self.root_handle
        elif isinstance(self.root_handle, str):
            logger.info('handle is handle string. oas use it as root handle title')
            if handle_title2num(self.root_handle) !=0:
                self.root_handle_num = handle_title2num(self.root_handle)
                self.root_handle_title = self.root_handle
        logger.info(f'the root handle title is {self.root_handle_title} and num is {self.root_handle_num}')

        # 获取句柄树
        self.root_node = WindowNode(name=self.root_handle_title, num=self.root_handle_num)
        Handle.handle_tree(self.root_handle_num, self.root_node)
        logger.info('the emulator handle structure is')
        for pre, fill, node in RenderTree(self.root_node):
            logger.info("%s%s" % (pre, node.name))

    @staticmethod
    def all_windows() -> list:
        """
        获取桌面上的所有窗体

        :return:  类似这样['MuMu模拟器']
        """

        def enum_windows_callback(hwnd, windows):
            window_text = GetWindowText(hwnd)
            windows.append(window_text)

        windows = []
        EnumWindows(enum_windows_callback, windows)
        return windows

    @classmethod
    def auto_handle_title(cls, windows: list) -> str:
        """
        返回第一个找到的有模拟器的标题
        :param windows:
        :return:
        """
        if windows is None:
            logger.error("handle_auto not get all wnidow")

        for window_title in windows:
            for item in Handle.emulator_list:
                if window_title.find(item) != -1:
                    logger.info(f'handle auto seclect to find {window_title} and use it as root_title')
                    return window_title

        return None

    @staticmethod
    def handle_tree(hwnd, node: WindowNode, level: int =0) -> None:
        """
        生成一个窗口的句柄树
        :param hwnd:
        :param node:
        :param level:
        :return:
        """
        child_windows = []
        EnumChildWindows(hwnd, lambda hwnd, param: param.append(hwnd), child_windows)

        if not child_windows:
            return
        for child_hwnd in child_windows:
            if GetParent(child_hwnd) == hwnd:
                child_text = GetWindowText(child_hwnd)
                child_node = WindowNode(name=child_text, num=child_hwnd, parent=node)

                # 递归遍历子窗体的子窗体
                Handle.handle_tree(child_hwnd, child_node, level + 1)

    @cached_property
    def emulator_family(self) -> str:
        """
        通过句柄标题来判断这个是那个模拟器大类
        :return:
        """
        for emu in Handle.emulator_list:
            if self.root_handle_title.find(emu) != -1:
                if emu == 'MuMu':
                    return 'mumu_player_family'
                elif emu == '雷电':
                    return 'ld_player_family'
                elif emu == '夜神':
                    return 'nox_player_family'
                elif emu == '蓝叠':
                    return 'bluestacks_player_family'
                elif emu == '逍遥':
                    return 'memu_player_family'

if __name__ == '__main__':
    h = Handle(config='oas1')
    logger.info(h.auto_handle_title(h.all_windows()))
    logger.info(h.root_handle_num)
    logger.info(h.emulator_family)

