
from module.logger import logger
from tasks.SixRealms.moon_sea.skills import MoonSeaSkills


class MoonSeaL101(MoonSeaSkills):
    def run_l101(self):
        logger.hr('Start l101')
        self.screenshot()
        if self.appear(self.I_STORE_SKILL_101):
            logger.info('Start purchase skill 101')
            self.screenshot()
            if not self.appear(self.I_STORE_SKILL_101):
                logger.warning('Skill 101 purchase failed')
            else:
                while 1:
                    self.screenshot()
                    if self.in_main():
                        break
                    if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1.5):
                        continue
                    if self.appear_then_click(self.I_UI_CONFIRM, interval=1.5):
                        continue
                    coin = self.O_COIN_NUM.ocr()
                    if coin < 300:
                        logger.info('Not enough coin')
                        break
                    if self.appear(self.I_STORE_SKILL_101, interval=3):
                        x, y = self.I_STORE_SKILL_101.front_center()
                        x -= 60
                        self.device.click(x=x, y=y,)
            while 1:
                self.screenshot()
                if self.in_main():
                    break
                if self.appear_then_click(self.I_L103_EXIT, interval=1.5):
                    continue
            logger.info('Finish purchase skill 101')


