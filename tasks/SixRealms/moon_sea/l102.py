
from module.logger import logger
from tasks.SixRealms.moon_sea.skills import MoonSeaSkills


class MoonSeaL102(MoonSeaSkills):
    def run_l102(self):
        logger.hr('Start Island battle')
        logger.info('Island 102')
        is_imitation = None
        while 1:
            self.screenshot()
            if self.appear(self.I_COIN_RIGHT_TOP):
                is_imitation = False
                break
            if self.appear(self.I_IMITATE):
                is_imitation = True
                break
        if not is_imitation:
            logger.info('Transfer skill')
            logger.info('Do not transfer skill and exit')
            while 1:
                self.screenshot()
                if self.in_main():
                    break
                if self.appear_then_click(self.I_UI_UNCHECK, interval=0.5):
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1.5):
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM, interval=1.5):
                    continue
                if self.appear_then_click(self.I_BACK_EXIT, interval=3):
                    continue
            logger.info('Finish Island 102')
            return
        self.imitate()

    def imitate(self):
        # 仿造
        logger.info('Imitate')
        cnt_imitate = 0
        while 1:
            self.screenshot()
            if self.in_main():
                break
            if self.appear_then_click(self.I_IMITATE_1, interval=2.5):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if cnt_imitate >= 3:
                logger.info('Finish Imitate Fail')
                logger.info('The most possible reason is that the skill is max level')
                while 1:
                    self.screenshot()
                    if self.in_main():
                        break
                    if self.appear_then_click(self.I_BACK_EXIT, interval=2):
                        continue
                break
            if self.appear_then_click(self.I_IMITATE, interval=1):
                cnt_imitate += 1
                continue
        self.cnt_skill101 += 1
        logger.info(f'Skill 101 level: {self.cnt_skill101}')
        logger.info('Finish Imitate')


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = MoonSeaL102(c, d)
    t.screenshot()

    t.run_l102()
