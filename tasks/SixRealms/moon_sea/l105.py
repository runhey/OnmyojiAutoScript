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
        if not self.wait_until_appear(self.I_ZHAOFU, wait_time=1):
            self.save_image(task_name="Island 105", image_type=True, wait_time=1)
            self.appear_then_click(self.I_BACK_EXIT, interval=1)
            return False
        while 1:
            self.screenshot()
            if self.appear(self.I_NPC_FIRE):
                break
            if self.appear_then_click(self.I_ZHAOFU):
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
        return True


if __name__ == '__main__':
    from module.config.config import Config

    c = Config('du')
    t = MoonSeaL105(c)
    t.screenshot()

    t.run_l105()
