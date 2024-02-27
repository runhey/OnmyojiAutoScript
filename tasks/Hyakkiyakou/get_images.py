import time

from module.atom.click import RuleClick
from module.atom.image import RuleImage
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from PIL import Image
from tasks.Hyakkiyakou.assets import HyakkiyakouAssets


class GetImages(GeneralBattle, GameUi, HyakkiyakouAssets):

    def run(self):
        self.screenshot()
        if self.appear_then_click(self.START):
            n = 0
            while 1:
                start = time.time()
                time.sleep(0.3)
                self.screenshot()
                if self.appear(self.END):
                    break
                n = n + 1
                # Image
                im = self.device.image
                img = Image.fromarray(im)
                # Inference
                img.save(f"./tasks/Hyakkiyakou/images/{time.time()}.jpg")
                end = time.time()
                print(end - start)


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas1')
    device = Device(config)
    t = GetImages(config, device)
    t.run()
