from module.logger import logger
from tasks.SixRealms.moon_sea.skills import MoonSeaSkills


class MoonSeaMap(MoonSeaSkills):

    def enter_island(self):
        self.screenshot()
        if self.appear_then_click_and_wait(self.I_UI_CANCEL, wait_time=1):
            return True
        if self.appear_then_click_and_wait(self.I_SHENMI, wait_time=1):
            return True
        if self.appear_then_click_and_wait(self.I_HUNDUN, wait_time=1):
            return True
        if self.appear_then_click_and_wait(self.I_ZHAN, wait_time=1):
            return True
        if self.appear_then_click_and_wait(self.I_XING, wait_time=1):
            return True
        if self.appear_then_click_and_wait(self.I_NINGXI, wait_time=1):
            return True
        logger.info('Entering island')
        return None

    def activate_store(self) -> bool:
        """
        最后打boss前面激活一次商店买东西
        @return: 有钱够就是True
        """
        if self.cnt_skill101 >= 5:
            # 如果柔风满级就不召唤
            return False
        self.screenshot()
        if not self.appear_rgb(self.I_M_STORE_ACTIVITY):
            return False
        cnt_act = 0
        logger.info('Activating store')
        while 1:
            self.screenshot()
            if self.appear(self.I_UI_CONFIRM):
                self.ui_click_until_disappear(self.I_UI_CONFIRM, interval=2)
                break
            if cnt_act >= 3:
                logger.warning('Store is not active')
                return False
            if self.appear_then_click(self.I_M_STORE_ACTIVITY, interval=1.5):
                cnt_act += 1
                continue
        return True


if __name__ == '__main__':
    from module.config.config import Config

    c = Config('du')
    t = MoonSeaMap(c)
    # t.screenshot()
    # t.device.image = load_image(r'C:\Users\Ryland\Desktop\Desktop\34.png')
    # match = re.search(r'\d{1,2}', '<17回合后迎战月读')
    # if match:
    #     isl_num = int(match.group())
    #     print(isl_num)

