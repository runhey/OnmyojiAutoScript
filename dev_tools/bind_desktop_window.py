# -*- coding: utf-8 -*-
"""
桌面客户端窗口 PID 绑定工具
============================
把"阴阳师-网易游戏"桌面客户端窗口的 PID 写入指定 OAS 配置，并切到桌面模式
（serial='desktop'、handle=PID、screenshot_method='window_background'、control_method='window_message'）。

用法:
    ./toolkit/python.exe -m dev_tools.bind_desktop_window --config oas1 --pick
    ./toolkit/python.exe -m dev_tools.bind_desktop_window --config oas1 --list
    ./toolkit/python.exe -m dev_tools.bind_desktop_window --config oas1 --pid 4242
"""
import argparse
import ctypes
import sys
from ctypes import wintypes

import win32gui
import win32process

from module.config.config import Config
from module.logger import logger

DESKTOP_WINDOW_TITLES = ('阴阳师-网易游戏', '阴阳师-MuMu模拟器专版')


def list_desktop_windows() -> list:
    """枚举所有桌面客户端窗口，返回 [(title, hwnd, pid)]。"""
    def enum_cb(hwnd, param):
        param.append(hwnd)
        return True

    windows = []
    win32gui.EnumWindows(enum_cb, windows)
    result = []
    for hwnd in windows:
        title = win32gui.GetWindowText(hwnd)
        if title in DESKTOP_WINDOW_TITLES:
            pid = win32process.GetWindowThreadProcessId(hwnd)[1]
            result.append((title, hwnd, pid))
    return result


def pick_window_under_cursor() -> int:
    """返回鼠标光标所指窗口的句柄；无窗口返回 0。"""
    user32 = ctypes.WinDLL('user32', use_last_error=True)

    class POINT(ctypes.Structure):
        _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

    point = POINT()
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    if not user32.GetCursorPos(ctypes.byref(point)):
        return 0
    user32.WindowFromPoint.argtypes = [POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    return int(user32.WindowFromPoint(point)) or 0


def bind_pid_to_config(config_name: str, pid: int) -> None:
    """把 PID 写入指定配置，并切到桌面模式。"""
    config = Config(config_name)
    config.script.device.serial = 'desktop'
    config.script.device.handle = str(pid)
    # PrintWindow 对客户端的 DirectX 渲染窗口返回纯黑，桌面模式统一用 BitBlt
    config.script.device.screenshot_method = 'window_background'
    config.script.device.control_method = 'window_message'
    config.save()
    logger.info(f'Config [{config_name}] bound to desktop client PID={pid}')
    # 绑定后检测并调整窗口客户区到 1280x720，保证识别 1:1
    from module.device.handle import Handle
    h = Handle(config)
    h.desktop_window_set_size()


def main():
    parser = argparse.ArgumentParser(description='绑定桌面客户端窗口 PID 到 OAS 配置')
    parser.add_argument('--config', required=True, help='配置实例名，如 oas1')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--pick', action='store_true', help='鼠标点选窗口（光标所指）')
    group.add_argument('--list', action='store_true', help='从窗口列表按序号选择')
    group.add_argument('--pid', type=int, help='直接指定 PID')
    args = parser.parse_args()

    if args.pid:
        bind_pid_to_config(args.config, args.pid)
        return

    if args.pick:
        input('请把鼠标移到目标游戏窗口上，然后按回车…')
        hwnd = pick_window_under_cursor()
        if not hwnd:
            logger.error('未获取到光标下的窗口')
            sys.exit(1)
        title = win32gui.GetWindowText(hwnd)
        if title not in DESKTOP_WINDOW_TITLES:
            logger.error(f'光标下的窗口不是桌面客户端（标题: "{title}"），'
                         f'请把鼠标移到游戏画面实体区域上重试')
            sys.exit(1)
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        bind_pid_to_config(args.config, pid)
        return

    windows = list_desktop_windows()
    if not windows:
        logger.error('未找到桌面客户端窗口，请先启动游戏')
        sys.exit(1)
    for i, (title, hwnd, pid) in enumerate(windows):
        print(f'[{i}] {title}  PID={pid}  HWND=0x{hwnd:X}')
    choice = input('请输入方括号内的序号: ')
    idx = int(choice)
    _, _, pid = windows[idx]
    bind_pid_to_config(args.config, pid)


if __name__ == '__main__':
    main()
