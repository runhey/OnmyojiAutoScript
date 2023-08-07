# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from module.logger import logger
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr

from tasks.RichMan.mall.special import Special
from tasks.RichMan.config import FriendshipPoints as FriendshipPointsConfig


class FriendshipPoints(Special):

    def execute_friendship(self, con: FriendshipPointsConfig = None):
        if not con:
            con = self.config.rich_man.friendship_points
        if not con.enable:
            logger.info('Friendship points is not enable')
            return
        self._enter_friendship()

        # 购买
        if con.white_daruma:
            self.buy_mall_one(buy_button=self.I_FS_WHITE_CLICK, buy_check=self.I_FS_WHITE_CHECK,
                              money_ocr=self.O_MALL_RESOURCE_5, buy_money=1000)
        if con.red_daruma != 0:
            self.buy_mall_more(buy_button=self.I_FS_RED, remain_number=False, money_ocr=self.O_MALL_RESOURCE_5,
                                 buy_number=con.red_daruma, buy_max=99, buy_money=150)
        if con.broken_amulet != 0:
            self.buy_mall_more(buy_button=self.I_FS_BROKEN, remain_number=False, money_ocr=self.O_MALL_RESOURCE_5,
                                 buy_number=con.broken_amulet, buy_max=99, buy_money=100)

    def buy_mall_one(self, buy_button: RuleImage, buy_check: RuleImage, money_ocr: RuleOcr, buy_money: int):
        """
        针对只能买一个的
        :param buy_button:
        :param buy_check:
        :param money_ocr:
        :param buy_money: 买这一个花多少
        :return:
        """
        logger.hr(buy_button.name, 3)
        self.screenshot()
        # 检查是否出现了购买按钮
        if not self.appear(buy_button):
            logger.warning('Buy button is not appear')
            return False
        # 是否检查剩余数量
        _remain = self._special_check_remain(buy_button)
        if _remain == 0:
            logger.warning('Remain number is 0')
            return False
        # 检查钱
        current_money = money_ocr.ocr(self.device.image)
        if not isinstance(current_money, int):
            logger.warning('Money ocr failed')
            return False
        money_enough = current_money >= buy_money
        if not money_enough:
            logger.warning(f'No enough money {current_money}')
            return False
        # 点击购买
        return self.buy_one(buy_button, buy_check)

    def buy_mall_more(self, buy_button: RuleImage, remain_number: bool, money_ocr: RuleOcr,
                       buy_number: int, buy_max: int, buy_money: int):
        """
        针对可以买多个的
        :param money_ocr:  检查钱的第几个
        :param remain_number: 是否需要检查剩余数量
        :param buy_button:
        :param buy_number:
        :param buy_max:
        :param buy_money:
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
        # 是否检查剩余数量
        if remain_number:
            _remain = self._special_check_remain(buy_button)
            if _remain == 0:
                logger.warning('Remain number is 0')
                return
            if _remain < buy_number:
                logger.warning(f'Remain number is {_remain}, buy number is {buy_number}')
                buy_number = _remain
        # 检查钱够不够
        current_money = money_ocr.ocr(self.device.image)
        if not isinstance(current_money, int):
            logger.warning('Money ocr failed')
            return
        money_enough = current_money >= buy_money * buy_number
        if not money_enough:
            logger.warning(f'Money is not enough {current_money}')
            # 判断够不够买2个
            if current_money < buy_money * 2:
                logger.warning('Money is not enough 2')
                return
            buy_number = current_money // buy_money
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

    c = Config('test')
    d = Device(c)
    t = FriendshipPoints(c, d)

    t.execute_friendship()
