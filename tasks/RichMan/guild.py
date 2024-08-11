# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
import re

from module.logger import logger
from module.atom.image import RuleImage

from tasks.GameUi.page import page_main, page_guild
from tasks.GameUi.game_ui import GameUi
from tasks.Component.Buy.buy import Buy
from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import GuildStore

class Guild(Buy, GameUi, RichManAssets):

    def execute_guild(self, con: GuildStore=None):
        logger.hr('Start guild', 1)
        self.ui_get_current_page()
        self.ui_goto(page_guild)
        while 1:
            self.screenshot()
            if self.appear(self.I_GUILD_CLOSE_RED):
                break
            if self.appear_then_click(self.I_GUILD_SHRINE, interval=0.8):
                continue
            if self.appear_then_click(self.I_GUILD_STORE, interval=1.1):
                continue
        logger.info('Enter guild store success')
        time.sleep(0.5)
        while 1:
            self.screenshot()
            if self.appear(self.I_GUILD_SKIN):
                break
            if self.swipe(self.S_GUILD_STORE, interval=1.5):
                time.sleep(2)
                continue

        # 开始购买
        if con.mystery_amulet:
            self._guild_mystery_amulet()
        if con.black_daruma_scrap:
            self._guild_black_daruma_scrap()
        if con.skin_ticket:
            self._guild_skin_ticket(con.skin_ticket)

        # 回去
        while 1:
            self.screenshot()
            if self.appear(self.I_GUILD_SHRINE):
                break
            if self.appear_then_click(self.I_GUILD_CLOSE_RED, interval=1):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1):
                continue

    def _guild_mystery_amulet(self):
        logger.hr('Guild mystery amulet', 2)
        self.screenshot()
        if not self.buy_check_money(self.O_GUILD_TOTAL, 240):
            return False
        number = self.check_remain(self.I_GUILD_BLUE)
        if number == 0:
            logger.warning('No mystery amulet can buy')
            return False
        self.buy_more(self.I_GUILD_BLUE, number)
        time.sleep(0.5)
        return True

    def _guild_black_daruma_scrap(self):
        logger.hr('Guild black daruma scrap', 2)
        self.screenshot()
        if not self.buy_check_money(self.O_GUILD_TOTAL, 200):
            return False
        number = self.check_remain(self.I_GUILD_SCRAP)
        if number == 0:
            logger.warning('No black daruma can buy')
            return False
        self.buy_one(self.I_GUILD_SCRAP, self.I_GUILD_CHECK_SCRAP)
        time.sleep(0.5)
        return True

    def _guild_skin_ticket(self, num: int=0):
        logger.hr('Guild skin ticket', 2)
        if num == 0:
            logger.warning('No buy skin ticket')
            return False
        self.screenshot()
        if not self.buy_check_money(self.O_GUILD_TOTAL, 50):
            return False
        number = self.check_remain(self.I_GUILD_SKIN)
        if number == 0:
            logger.warning('No skin ticket can buy')
            return False
        self.buy_more(self.I_GUILD_SKIN, number)
        time.sleep(0.5)
        return True

    def check_remain(self, image: RuleImage) -> int:
        self.O_GUILD_REMAIN.roi[0] = image.roi_front[0] - 38
        self.O_GUILD_REMAIN.roi[1] = image.roi_front[1] + 83
        logger.info(f'Image roi {image.roi_front}')
        logger.info(f'Image roi {self.O_GUILD_REMAIN.roi}')
        self.screenshot()
        result = self.O_GUILD_REMAIN.ocr(self.device.image)
        result = result.replace('？', '2').replace('?', '2').replace(':', '；')
        try:
            result = re.findall(r'本周剩余数量(\d+)', result)[0]
            result = int(result)
        except:
            result = 0
        logger.info('Remain: %s' % result)
        return int(result)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = Guild(c, d)

    # t._guild_skin_ticket(5)
    t.execute_guild(con=c.rich_man.guild_store)


