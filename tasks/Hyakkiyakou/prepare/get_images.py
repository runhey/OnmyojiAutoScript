import cv2
import time
from datetime import timedelta, datetime
from cached_property import cached_property
from random import choice
from pathlib import Path

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_hyakkiyakou
from tasks.Hyakkiyakou.assets import HyakkiyakouAssets


class GenerateImages(GameUi, HyakkiyakouAssets):
    @cached_property
    def save_folder(self) -> Path:
        save_time = datetime.now().strftime('%Y%m%dT%H%M%S')
        save_folder = Path(f'./tasks/Hyakkiyakou/temp/{save_time}')
        save_folder.mkdir(parents=True, exist_ok=True)
        return save_folder

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_hyakkiyakou)
        for i in range(20):
            self.save_one()

    def save_one(self):
        """
        生成一次票的截图
        @return:
        """
        if not self.appear(self.I_HACCESS):
            logger.warning('Page Error')
        self.ui_click(self.I_HACCESS, self.I_HSTART, interval=2)
        # 随机选一个
        click_button = choice([self.C_HSELECT_1, self.C_HSELECT_2, self.C_HSELECT_3])
        while 1:
            self.screenshot()

            if self.appear(self.I_CHECK_RUN):
                break
            if self.appear_then_click(self.I_HSTART, interval=2):
                continue
            if not self.appear(self.I_HSELECTED):
                self.click(click_button, interval=1)
        self.device.stuck_record_add('BATTLE_STATUS_S')
        # 保存图片
        save_img_timer = Timer(0.4)
        save_img_timer.start()
        while 1:
            self.screenshot()
            if self.appear(self.I_HEND):
                logger.info('Generate a time Images Success')
                break
            if not self.appear(self.I_CHECK_RUN):
                continue
            if self.appear(self.I_HFREEZE):
                continue
            if save_img_timer.reached():
                save_img_timer.reset()
                self.save_image()
        self.ui_click(self.I_HEND, self.I_HACCESS)

    def save_image(self, image=None):
        if image is None:
            image = self.device.image
        img1 = image[80:, :640]
        img2 = image[80:, 640:]
        # 时间戳毫秒级别
        time_now1 = int(time.time() * 1000)
        time_now2 = time_now1 + 1
        cv2.imwrite(str(self.save_folder / f'{time_now1}.png'), img1)
        cv2.imwrite(str(self.save_folder / f'{time_now2}.png'), img2)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = GenerateImages(c, d)
    t.screenshot()

    t.run()


