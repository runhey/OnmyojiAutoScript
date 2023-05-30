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
        self.menu['Script'] = ['Script', 'General', 'Restart']
        # 日常的任务
        self.menu["DailyTask"] = ['TerritorialDemon', 'CoinChallenge']

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
