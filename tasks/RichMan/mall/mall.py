# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from module.logger import logger

from tasks.RichMan.mall.special import Special
from tasks.RichMan.mall.friendship_points import FriendshipPoints
from tasks.RichMan.mall.medal import Medal
from tasks.RichMan.mall.charisma import Charisma
from tasks.RichMan.mall.consignment import Consignment
from tasks.RichMan.mall.scales import Scales
from tasks.RichMan.mall.honor import Honor
from tasks.RichMan.mall.bondlings import Bondlings
from tasks.GameUi.page import page_main, page_mall

class Mall(Medal, Charisma, Honor, Consignment, Scales, Bondlings):


    def execute_mall(self):
        logger.hr('Mall', 1)
        self.ui_get_current_page()
        self.ui_goto(page_mall, confirm_wait=2.5)

        # 寄售屋
        self.execute_consignment()
        # 蛇皮
        self.execute_scales()
        # 契灵
        self.execute_bondlings()

        # 杂货铺
        self.execute_special()
        self.execute_honor()
        self.execute_friendship()
        self.execute_medal()
        self.execute_charisma()

        # 退出
        self.back_mall()
