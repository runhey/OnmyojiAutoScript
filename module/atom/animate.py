from pathlib import Path
from module.logger import logger

from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.long_click import RuleLongClick
from module.atom.ocr import RuleOcr


class RuleAnimate(RuleImage):

    def __init__(self,
                 rule: RuleImage | RuleClick | RuleLongClick | RuleOcr,
                 threshold: float = 0.75,
                 name: str = None):
        if isinstance(rule, RuleImage):
            roi_front = rule.roi_front
            roi_back = rule.roi_back
            self._name = Path(rule.file).stem.upper()
            threshold = threshold
        elif isinstance(rule, RuleClick) or isinstance(rule, RuleLongClick):
            roi_front = rule.roi_front
            roi_back = rule.roi_back
            self._name = rule.name
        elif isinstance(rule, RuleOcr):
            roi_front = rule.roi
            roi_back = rule.area
            self._name = rule.name
        else:
            roi_front = None
            roi_back = None
            self._name = 'RuleAnimate'

        super().__init__(
            roi_front=list(roi_front),
            roi_back=list(roi_back),
            method='Template matching',
            threshold=threshold,
            file=''
        )

        if name is not None:
            self._name = name
        self._last_image = None

    @property
    def name(self) -> str:
        return self._name.upper()

    def stable(self, image) -> bool:
        """
        用于判断连续的两张截图，的目标区域是否一致
        @param image:
        @return:
        """
        if self._last_image is None:
            self._last_image = image
            return False

        self._image = self._last_image
        matched = self.match(image)
        self._last_image = self.corp(image, self.roi_front)

        if matched:
            logger.info(f'Animation Stable @ {self.name}')
            return True
        return False


if __name__ == '__main__':
    from module.base.utils import load_image
    from tasks.SixRealms.assets import SixRealmsAssets
    ttt = RuleAnimate(SixRealmsAssets.C_MAIN_ANIMATE_KEEP, threshold=0.5)
    imga = r'C:\Users\Ryland\Desktop\Desktop\37.png'
    imgb = r'C:\Users\Ryland\Desktop\Desktop\38.png'
    imga = load_image(imga)
    imgb = load_image(imgb)

    print(ttt.stable(imga))
    print(ttt.stable(imgb))
    print(ttt.stable(imgb))

