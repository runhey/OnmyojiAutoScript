# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum

class ShikigamiClass(str, Enum):
    SP = 'SP'
    SSR = 'SSR'
    SR = 'SR'
    R = 'R'
    N = 'N'
    # 材料
    MATERIAL = 'MATERIAL'
