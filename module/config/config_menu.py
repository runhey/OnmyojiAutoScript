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
        self.menu['TaskList'] = []
        # 脚本设置
        self.menu['Script'] = ['Script', 'Restart', 'GlobalGame']
        # 刷御魂
        self.menu["Soul Zones"] = ['Orochi', 'Sougenbi', 'FallenSun', 'EternitySea', 'SixRealms']
        # 日常的任务
        self.menu["Daily Task"] = ['DailyTrifles', 'AreaBoss', 'GoldYoukai', 'ExperienceYoukai', 'Nian',
                                   'TalismanPass', 'DemonEncounter', 'Pets', 'SoulsTidy', 'Delegation', 'WantedQuests',
                                   'Tako']
        # 很肝的任务
        self.menu["Liver Emperor Exclusive"] = [
            "BondlingFairyland",
            "EvoZone",
            "GoryouRealm",
            "Exploration",
            "Hyakkiyakou",
            "HeroTest",
        ]
        # 阴阳寮
        self.menu["Guild"] = ['KekkaiUtilize', 'KekkaiActivation', 'RealmRaid', 'RyouToppa', 'Dokan', 'CollectiveMissions',
                              'Hunt']
        # 每周任务
        self.menu["Weekly Task"] = ['TrueOrochi', 'RichMan', 'Secret', 'WeeklyTrifles', 'MysteryShop', 'Duel']
        # 活动的任务
        self.menu["Activity Task"] = ['ActivityShikigami', 'MetaDemon', 'FrogBoss', 'FloatParade', 'Quiz']
        # 开发工具
        self.menu["Tools"] = ['Image Rule', 'Ocr Rule', 'Click Rule', 'Long Click Rule', 'Swipe Rule', 'List Rule']

    @cached_property
    def gui_menu(self) -> str:
        """
        生成的是json字符串
        :return:
        """
        return json.dumps(self.menu, ensure_ascii=False, sort_keys=False, default=str)

    @cached_property
    def gui_menu_list(self) -> dict:
        del self.menu['TaskList']
        del self.menu['Tools']
        return self.menu


if __name__ == "__main__":
    try:
        m = ConfigMenu()
        print(m.gui_menu)
    except:
        print('weih')
