# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
import time

from module.logger import logger

from tasks.GameUi.page import page_main, page_guild
from tasks.GameUi.game_ui import GameUi
from tasks.Component.Buy.buy import Buy
from tasks.RichMan.assets import RichManAssets



class MallNavbar(GameUi, RichManAssets):

    def _enter_consignment(self):
        """
        进入寄售屋
        :return:
        """
        self.ui_click(self.I_MALL_CONSIGNMENT, self.I_MALL_CONSIGNMENT_CHECK)

    def _enter_scales(self):
        """
        进入密卷屋 蛇皮
        :return:
        """
        self.ui_click(self.I_MALL_SCCALES, self.I_MALL_SCCALES_CHECK)

    def _enter_bondlings(self):
        """
        进入契灵
        :return:
        """
        self._enter_scales()
        self.ui_click(self.I_MALL_BONDLINGS_SURE, self.I_MALL_BONDLINGS_ON)

    def _enter_sundry(self):
        """
        进入杂货铺
        :return:
        """
        self.ui_click(self.I_MALL_SUNDRY, self.I_MALL_SUNDRY_CHECK)

    def _enter_special(self):
        """
        进入特殊
        :return:
        """
        self._enter_sundry()
        self.ui_click(self.I_SIDE_SURE_SPECIAL, self.I_SIDE_CHECK_SPECIAL)

    def _enter_honor(self):
        """
        进入荣誉 屋
        :return:
        """
        self._enter_sundry()
        self.ui_click(self.I_SIDE_SUER_HONOR, self.I_SIDE_CHECK_HONOR)

    def _enter_friendship(self):
        """
        友情点
        :return:
        """
        self._enter_sundry()
        self.ui_click(self.I_SIDE_SURE_FRIENDS, self.I_SIDE_CHECK_FRIENDS)

    def _enter_medal(self):
        """
        勋章
        :return:
        """
        self._enter_sundry()
        self.ui_click(self.I_SIDE_SURE_MEDAL, self.I_SIDE_CHECK_MEDAL)

    def _enter_charisma(self):
        """
        魅力
        :return:
        """
        self._enter_sundry()
        self.ui_click(self.I_SIDE_SURE_CHARISMA, self.I_SIDE_CHECK_CHARISMA)

    def back_mall(self):
        """
        返回商城
        :return:
        """
        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_MALL)

    def mall_resource(self, index: int) -> int:
        """
        获取商城资源，
        :param index: 从左开始数
        :return:
        """
        match = {
            1: self.O_MALL_RESOURCE_1,
            2: self.O_MALL_RESOURCE_2,
            3: self.O_MALL_RESOURCE_3,
            4: self.O_MALL_RESOURCE_4,
            5: self.O_MALL_RESOURCE_5,
            6: self.O_MALL_RESOURCE_6,
        }
        self.screenshot()
        result = match[index].ocr(self.device.image)
        # match = re.search(r'\d+', result)
        # result = int(match.group())
        if not isinstance(result, int):
            logger.warning(f'Get mall resource {index} error, result: {result}')
        if result == 0:
            logger.warning(f'Get mall resource {index} error, result: {result}')
        return result

    def mall_check_money(self, index: int, least: int) -> bool:
        return self.mall_resource(index) >= least

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = MallNavbar(c, d)

