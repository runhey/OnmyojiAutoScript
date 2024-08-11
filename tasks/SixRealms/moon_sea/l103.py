
from module.logger import logger
from tasks.SixRealms.moon_sea.skills import MoonSeaSkills


class MoonSeaL103(MoonSeaSkills):
    def run_103(self):
        # 宝箱还是精英
        logger.hr('Island 103')
        self.wait_until_appear(self.I_ISLAND_TAG_FLAG, wait_time=2)
        is_box: bool = self.appear(self.I_L103_EXIT)
        if is_box:
            logger.info('Access to Box')
            while 1:
                self.screenshot()
                if self.appear(self.I_M_STORE):
                    logger.info('Not punched the treasure  box')
                    return
                if self.appear_then_click(self.I_UI_UNCHECK, interval=0.5):
                    continue
                if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                    continue
                if self.appear_then_click(self.I_L103_EXIT, interval=4):
                    continue
        self.battle_l103()
        logger.info('Island 103 Finished')

    def battle_l103(self):
        # 打精英
        logger.info('Start Island battle')
        while 1:
            self.screenshot()
            if self.appear(self.I_NPC_FIRE):
                break
            if self.click(self.C_NPC_FIRE_CENTER, interval=4):
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
    t = MoonSeaL103(c, d)
    t.screenshot()

    t.run_103()
