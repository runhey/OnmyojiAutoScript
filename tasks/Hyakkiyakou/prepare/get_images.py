from datetime import timedelta, datetime, time
from cached_property import cached_property

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_hyakkiyakou
from tasks.Hyakkiyakou.assets import HyakkiyakouAssets


class GenerateImages(GameUi, HyakkiyakouAssets):
    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_hyakkiyakou)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = GenerateImages(c, d)
    t.screenshot()

    t.run()

