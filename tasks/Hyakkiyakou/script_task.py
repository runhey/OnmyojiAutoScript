import torch

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from module.atom.click import RuleClick
from tasks.Hyakkiyakou.assets import HyakkiyakouAssets


class ScriptTask(GeneralBattle, GameUi, HyakkiyakouAssets):

    def run(self):
        # Model
        model = torch.hub.load('ultralytics/yolov5', 'custom', path='./tasks/Hyakkiyakou/weights/best.onnx')
        # local model
        # model = torch.hub.load('D:\project\pycharmproject\yolov5', 'custom', path='./tasks/Hyakkiyakou/weights/best.onnx',
        #                        source='local')

        n = 0
        self.screenshot()
        if self.appear_then_click(self.START):
            while 1:
                self.screenshot()
                if self.appear(self.END):
                    break
                # Inference
                results = model(self.device.image, size=640)
                # 过滤模型
                xmins = results.pandas().xyxy[0]['xmin']
                ymins = results.pandas().xyxy[0]['ymin']
                xmaxs = results.pandas().xyxy[0]['xmax']
                ymaxs = results.pandas().xyxy[0]['ymax']
                names = results.pandas().xyxy[0]['name']
                confidences = results.pandas().xyxy[0]['confidence']
                rightPoint = []
                n = n + 1
                for xmin, ymin, xmax, ymax, name, conf in zip(xmins, ymins, xmaxs, ymaxs, names, confidences):
                    if not rightPoint:
                        rightPoint = [xmin, ymin, xmax - xmin, ymax - ymin]
                    elif rightPoint[0] > xmin:
                        rightPoint = [xmin, ymin, xmax - xmin, ymax - ymin]
                if rightPoint:
                    click = RuleClick(roi_front=(rightPoint[0], rightPoint[1], rightPoint[2], rightPoint[3]),
                                      roi_back=(rightPoint[0], rightPoint[1], rightPoint[2], rightPoint[3]), name=n)
                    self.click(click)


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas1')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()
