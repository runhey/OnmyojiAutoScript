# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import json

from cached_property import cached_property
from pydantic import BaseModel, ValidationError, validator, Field

from module.config.utils import *

class ConfigMenu:
    # 手动的代码配置菜单
    def __init__(self) -> None:
        self.menu = {}
        # 总览
        self.menu["Overview"] = []
        # 脚本设置
        self.menu['Script'] = ['Script', 'General', 'Restart', 'GlobalGame']
        # 开发工具
        self.menu["Tools"] = ['Image Rule', 'Ocr Rule', 'Click Rule', 'Long Click Rule', 'Swipe Rule']
        # 刷御魂
        self.menu["Soul Zones"] = ['Orochi', 'OrochiMoans', 'OrochiJudgement', 'Sougenbi', 'FallenSun', 'EternitySea']
        # 日常的任务
        self.menu["Daily Task"] = ['AreaBoss', 'GoldYoukai', 'ExperienceYoukai', 'Nian']
    @cached_property
    def gui_menu(self) -> str:
        """
        生成的是json字符串
        :return:
        """
        return json.dumps(self.menu, ensure_ascii=False, sort_keys=False, default=str)

if __name__ == "__main__":
    try:
        m = ConfigMenu()
        print(m.gui_menu)
    except:
        print('weih')
