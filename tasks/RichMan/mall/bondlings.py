# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from module.logger import logger
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr

from tasks.GameUi.page import page_main, page_guild
from tasks.RichMan.mall.navbar import MallNavbar
from tasks.Component.Buy.buy import Buy
from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import Bondlings as BondlingsConfig


class Bondlings(Buy, MallNavbar):

    def execute_bondlings(self, con: BondlingsConfig = None):
        if not con:
            con = self.config.rich_man.bondlings
        if not con.enable:
            logger.info('Bondlings is disable')
            return
        self._enter_bondlings()

        # 购买石头
        self._bondlings_base(buy_button=self.I_BL_BUY_STONE, remain_number=self.O_BL_RES_STONE, check_class=2,
                             buy_number=con.bondling_stone, buy_max=10, buy_money=30)
        # 购买御魂
        self._bondlings_base(buy_button=self.I_BL_BUY_SOULS, remain_number=self.O_BL_RES_SOULS, check_class=1,
                             buy_number=con.random_soul, buy_max=25, buy_money=20)
        # 购买高级盘
        self._bondlings_base(buy_button=self.I_BL_BUY_HIGH, remain_number=self.O_BL_RES_HIGH, check_class=3,
                             buy_number=con.high_bondling_discs, buy_max=10, buy_money=50)
        # 购买中级盘
        self._bondlings_base(buy_button=self.I_BL_BUY_MEDIUM, remain_number=self.O_BL_RES_MEDIUM, check_class=4,
                             buy_number=con.medium_bondling_discs, buy_max=25, buy_money=20)

    def _bondlings_base(self, buy_button: RuleImage, remain_number: RuleOcr, check_class: int,
                       buy_number: int, buy_max: int, buy_money: int):
        """

        :param buy_button: 对应的兑换按钮
        :param remain_number: 对应的检查剩余数量的ocr
        :param check_money: 对应的检查剩余金钱的第一个
        :param buy_number: 购买多少
        :param buy_max: 这一个种类一次性最多购买多少
        :param buy_money: 每一个购买的钱数
        :return:
        """
        logger.hr(buy_button.name, 3)
        if buy_number == 0:
            logger.info('Buy number is 0')
            return
        self.screenshot()
        # 检查是否出现了购买按钮
        if not self.appear(buy_button):
            logger.warning('Buy button is not appear')
            return
        # 检查剩余数量
        _remain = remain_number.ocr(self.device.image)
        if _remain == 0:
            logger.warning('Remain number is 0')
            return
        if _remain < buy_number:
            logger.warning(f'Remain number is {_remain}, buy number is {buy_number}')
            buy_number = _remain
        # 检查金钱
        cu, re, total = self.O_BL_CHECK_MONEY.ocr(self.device.image)
        if cu + re != total:
            logger.warning('Check money is error')
            logger.warning(f'cu: {cu}, re: {re}, total: {total}')
            return
        money_enough = cu >= buy_money * buy_number
        if not money_enough:
            logger.warning(f'Money is not enough {cu}')
            # 判断够不够买2个
            if cu < buy_money * 2:
                logger.warning('Money is not enough 2')
                return
            buy_number = cu // buy_money
        # 购买
        logger.info(f'Buy number is {buy_number}')
        if buy_number >= buy_max:
            buy_cycles_number = buy_number // buy_max
            buy_res_number = buy_number % buy_max
        else:
            buy_cycles_number = None
            buy_res_number = buy_number

        if buy_cycles_number:
            for i in range(buy_cycles_number):
                self.buy_more(buy_button)
                time.sleep(0.5)
        if buy_res_number:
            self.buy_more(buy_button, buy_res_number)
            time.sleep(0.5)





if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = Bondlings(c, d)

    t.execute_bondlings()


