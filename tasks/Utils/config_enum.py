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


class DemonClass(str, Enum):
    # tsuchigumo 土蜘蛛
    TSUCHIGUMO = '土蜘蛛'
    # oboroguruma 胧车
    OBOROGURUMA = '胧车'
    # odokuro 荒骷髅
    ODOKURO = '荒骷髅'
    # namazu 地震鲇
    NAMAZU = '地震鲇'
    # shinkiro 蜃气楼
    SHINKIRO = '蜃气楼'
    # ghostly songstress 鬼灵歌伎
    GHOSTLY_SONGSTRESS = '鬼灵歌伎'






