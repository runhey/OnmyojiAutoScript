# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum

class MainType(str, Enum):
    COSTUME_MAIN = 'costume_main'  # 初语谧景
    COSTUME_MAIN_1 = 'costume_main_1'  # 织梦莲庭
    COSTUME_MAIN_2 = 'costume_main_2'  # 琼夜淬光
    COSTUME_MAIN_3 = 'costume_main_3'  # 烬夜韶阁
    COSTUME_MAIN_4 = 'costume_main_4'  # 笔墨山河
    COSTUME_MAIN_5 = 'costume_main_5'  # 枫色秋庭


class CostumeConfig(BaseModel):
    # 皮肤配置
    costume_main_type: MainType = Field(default=MainType.COSTUME_MAIN, description='costume_main_type_help')







