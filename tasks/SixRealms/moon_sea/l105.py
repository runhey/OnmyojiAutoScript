from module.logger import logger
from tasks.SixRealms.moon_sea.skills import MoonSeaSkills


class MoonSeaL105(MoonSeaSkills):

    def run_l105(self):
        """
        打最普通的小怪是没有任何技能的
        @return:
        """
        logger.hr('Start Island battle')
        logger.info('Island 105')
        while 1:
            self.screenshot()
            if self.appear(self.I_NPC_FIRE):
                break
            if self.click(self.C_NPC_FIRE_LEFT):
                continue
        self.battle_lock_team()
        self.island_battle()
        logger.info('Island battle finished')
        while 1:
            self.screenshot()
            if self.in_main():
                break
            if self.appear_then_click(self.I_COIN, action=self.C_UI_REWARD, interval=0.8):
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = MoonSeaL105(c, d)
    t.screenshot()

    t.run_l105()
