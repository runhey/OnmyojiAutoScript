# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import ctypes
import win32gui
import win32con
import sys
import time

from pathlib import Path
from module.logger import logger

def get_work_path() -> Path:
    """
    返回程序工作的目录如果没有问题的就是根目录
    """
    return Path.cwd()


def is_admin():
    """
    Check if the program is running as an admin.
    """
    try:
        result = ctypes.windll.shell32.IsUserAnAdmin()
        return result == 1
    except:
        return False

def check_admin():
    """
    检查是不是管理员权限
    如果不是管理员权限则使用管理员权限重启
    """
    if not is_admin():
        logger.info('非管理员身份运行，已尝试以管理员身份运行')
        time.sleep(5)
        # Hide the command window
        # win = win32gui.GetForegroundWindow()
        # win32gui.ShowWindow(win, win32con.SW_HIDE)
        # Re-run the program as an admin
        args = ' '.join(sys.argv)
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
        sys.exit(0)
    logger.log('管理员身份运行')

