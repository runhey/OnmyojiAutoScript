import time

from module.atom.click import RuleClick
from module.atom.image import RuleImage
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from PIL import Image


class GetImages(GeneralBattle, GameUi, SwitchSoul):

    def run(self):
        end = RuleImage(roi_front=(0, 0, 246, 78), roi_back=(0, 0, 1240, 700), threshold=0.8,
                        method="Template matching",
                        file="./res/end.png")
        test = RuleImage(roi_front=(1116, 556, 110, 85), roi_back=(0, 0, 1240, 700), threshold=0.8,
                         method="Template matching",
                         file="./res/start.png")
        self.screenshot()
        if self.appear_then_click(test):
            n = 0
            while 1:
                time.sleep(0.5)
                self.screenshot()
                if self.appear(end):
                    break
                n = n + 1
                # Image
                im = self.device.image
                img = Image.fromarray(im)
                # Inference
                img.save(f"./images/image{n}.jpg")


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas1')
    device = Device(config)
    t = GetImages(config, device)
    t.run()
