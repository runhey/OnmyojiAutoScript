
from module.logger import logger
from tasks.SixRealms.moon_sea.skills import MoonSeaSkills


class MoonSeaL104(MoonSeaSkills):
    def run_l104(self):
        logger.hr('Start Island battle')
        logger.info('Island 104')
        while 1:
            self.screenshot()
            if self.appear(self.I_NPC_FIRE):
                break
            if self.click(self.C_NPC_FIRE_RIGHT, interval=4):
                continue
        self.battle_lock_team()
        self.island_battle()
        logger.info('Island battle finished')
        self.select_skill(refresh=True)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = MoonSeaL104(c, d)
    t.screenshot()

    t.run_l104()

