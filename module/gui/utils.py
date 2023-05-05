# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pathlib import Path

def get_work_path() -> Path:
    """
    返回程序工作的目录如果没有问题的就是根目录
    """
    return Path.cwd()