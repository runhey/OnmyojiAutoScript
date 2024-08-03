import re
import time
from module.logger import logger
from module.base.timer import Timer
from tasks.SixRealms.moon_sea.skills import MoonSeaSkills


class MoonSeaL101(MoonSeaSkills):

    def buy_skill_101(self) -> bool:
        logger.info('Buy skill 101')
        self.wait_animate_stable(self.C_STORE_ANIMATE_KEEP, timeout=2)
        self.wait_until_appear(self.I_STORE_STABLE_FLAG)
        buy_try: int = 0
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1.5):
                break
            if self.appear(self.I_UI_CONFIRM):
                break
            if buy_try >= 4:
                logger.warning(f'Buy skill 101 failed')
                return False
            if self.appear(self.I_STORE_SKILL_101, interval=3):
                x, y = self.I_STORE_SKILL_101.front_center()
                x -= 60
                self.device.click(x=x, y=y, )
                buy_try += 1
        self.ui_click_until_disappear(self.I_UI_CONFIRM)
        self.wait_until_appear(self.I_STORE_EXIT)
        self.cnt_skill101 += 1
        logger.info(f'Skill 101 level: {self.cnt_skill101}')
        logger.info('Buy skill 101 done')
        return True

    def refresh_store(self) -> bool:
        # 刷新宁溪
        # 只会点击一次
        logger.info('Refresh store')
        text = self.O_STORE_REFRESH_TIME.ocr(self.device.image)
        matches = re.search(f"剩\d+次", text)
        if matches:
            refresh_time = int(matches.group()[1])
            logger.info(f'Refresh time: {refresh_time}')
            if refresh_time <= 0:
                logger.warning('Refresh time is 0')
                return False
        cnt_refresh = 0
        # while 1:
        #     self.screenshot()
        #     if self.appear(self.I_UI_CONFIRM):
        #         break
        #     if self.appear_then_click(self.I_STORE_REFRESH, interval=1.5):
        #         cnt_refresh += 1
        #         continue
        #     if cnt_refresh >= 1:
        #         return False
        # self.ui_click_until_disappear(self.I_UI_CONFIRM, interval=2)
        # self.wait_until_appear(self.I_STORE_EXIT)
        self.appear_then_click(self.I_STORE_REFRESH, interval=1.5)
        self.wait_until_stable(self.I_UI_CONFIRM, timeout=Timer(2, count=10))
        logger.info('Refresh store done')
        return True

    def run_l101(self):
        logger.hr('Start l101')
        logger.info('Keep buying skills until you run out of money')
        self.wait_until_appear(self.I_STORE_EXIT)
        self.wait_animate_stable(self.C_STORE_ANIMATE_KEEP, timeout=2)
        if self.appear(self.I_UI_CANCEL):
            # 有时候点击进入商店太快了，就进入会选随机的一个
            self.ui_click_until_disappear(self.I_UI_CANCEL, interval=1)
        while 1:
            self.screenshot()
            coin = self.O_COIN_NUM.ocr(self.device.image)
            if coin < 300:
                logger.info('Not enough coin')
                break
            if self.cnt_skill101 >= 5:
                logger.info('Skill 101 level is max')
                break

            if self.appear(self.I_UI_CONFIRM):
                self.ui_click_until_disappear(self.I_UI_CONFIRM, interval=1)
            if self.appear(self.I_STORE_SKILL_101):
                self.buy_skill_101()
            elif coin < 400:
                break
            elif not self.refresh_store():
                break

        logger.info('Finish purchase skill 101')
        while 1:
            self.screenshot()
            if self.in_main():
                break
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_STORE_EXIT, interval=1):
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = MoonSeaL101(c, d)
    t.screenshot()

    t.run_l101()
