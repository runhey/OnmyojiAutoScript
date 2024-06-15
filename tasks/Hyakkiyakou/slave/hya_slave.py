import cv2

from cached_property import cached_property
from pathlib import Path

from module.logger import logger
from module.atom.image import RuleImage
from tasks.Hyakkiyakou.slave.hya_device import HyaDevice
from tasks.Hyakkiyakou.assets import HyakkiyakouAssets


class HyaSlave(HyaDevice, HyakkiyakouAssets):
    """
    主要是用来跟游戏进行交互的
    """
    # x, y, w, h
    HUNDRED0HUNDRED: list[int] = [117, 647, 18, 25]
    DECADE0HUNDRED: list[int] = [131, 647, 18, 25]
    UNIT0HUNDRED: list[int] = [146, 647, 18, 25]
    DECADE0DECADE: list[int] = [126, 647, 18, 25]
    UNIT0DECADE: list[int] = [140, 647, 18, 25]

    @cached_property
    def res_r(self) -> list[RuleImage]:
        return [
            self.I_RESR_0,
            self.I_RESR_1,
            self.I_RESR_2,
            self.I_RESR_3,
            self.I_RESR_4,
            self.I_RESR_5,
            self.I_RESR_6,
            self.I_RESR_7,
            self.I_RESR_8,
            self.I_RESR_9,
        ]

    @cached_property
    def res_f(self) -> list[RuleImage]:
        return [
            self.I_RESF_0,
            self.I_RESF_1,
            self.I_RESF_2,
            self.I_RESF_3,
            self.I_RESF_4,
            self.I_RESF_5,
            self.I_RESF_6,
            self.I_RESF_7,
            self.I_RESF_8,
            self.I_RESF_9,
        ]

    @cached_property
    def bean(self) -> list[RuleImage]:
        return [
            self.I_BEAN0,
            self.I_BEAN1,
            self.I_BEAN2,
            self.I_BEAN3,
            self.I_BEAN4,
            self.I_BEAN5,
            self.I_BEAN6,
            self.I_BEAN7,
            self.I_BEAN8,
            self.I_BEAN9,
        ]


    def predict_res(self, current: int) -> int:
        for i in range(current, current-5, -1):
            unit = i % 10
            unit_img = self.res_r[unit]
            if not self.appear(unit_img):
                continue
            decade = i // 10
            decade_img = self.res_f[decade]
            if not self.appear(decade_img):
                continue
            return i
        logger.warning(f'Cannot predict result, current: {current}')
        return current

    def predict_bean(self, current: int):
        possible_beans: list[int] = [current, current - 10, current - 20]
        for bean in possible_beans:
            if bean >= 100:
                decade = bean // 10 % 10
                decade_img = self.bean[decade]
                decade_img.roi_back = self.DECADE0HUNDRED
                if not self.appear(decade_img):
                    continue
                hundred = bean // 100
                hundred_img = self.bean[hundred]
                hundred_img.roi_back = self.HUNDRED0HUNDRED
                if not self.appear(hundred_img):
                    continue
                return bean

            else:
                decade = bean // 10
                decade_img = self.bean[decade]
                decade_img.roi_back = self.DECADE0DECADE
                if not self.appear(decade_img):
                    print(f'没有匹配十位{decade}')
                    continue
                unit = bean % 10
                unit_img = self.bean[unit]
                unit_img.roi_back = self.UNIT0DECADE
                if self.appear(unit_img):
                    print(f'匹配到{bean}')
                    return bean
                for i in range(10):
                    unit_img = self.bean[i]
                    unit_img.roi_back = self.UNIT0DECADE
                    if self.appear(unit_img):
                        return max(0, (bean // 10) * 10 + i)
        logger.warning(f'Cannot predict bean, current: {current}')
        return current


def covert_rgb():
    images_folders: Path = Path(r'E:\Project\OnmyojiAutoScript\tasks\Hyakkiyakou\temp\20240614T214216')
    save_folders = images_folders.parent / 'save14'
    save_folders.mkdir(parents=True, exist_ok=True)
    for file in images_folders.iterdir():
        if file.suffix != '.png':
            continue
        img = cv2.imread(str(file))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        cv2.imwrite(str(save_folders / file.name), img)

def test_predict_res():
    import timeit
    from module.config.config import Config
    from module.device.device import Device


    c = Config('oas1')
    d = Device(c)
    hd = HyaSlave(c, d)
    img = cv2.imread(r'E:\Project\OnmyojiAutoScript\tasks\Hyakkiyakou\temp\save\all1716691199364.png')
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    hd.device.image = img
    print(hd.predict_res(18))

    def do_test():
        hd.predict_res(18)
    execution_time = timeit.timeit(do_test, number=100)
    print(f"执行总的时间: {execution_time * 1000} ms")
    # total time is 36.2ms on my computer /cpu:AMD Ryzen 5 3550H with Radeon Vega Mobile
    # 0.362ms per predict_res


def test_predict_bean():
    import timeit
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    hd = HyaSlave(c, d)
    img = cv2.imread(r'E:\Project\OnmyojiAutoScript\tasks\Hyakkiyakou\temp\save14\170.png')
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    hd.device.image = img
    print(hd.predict_bean(200))
    def do_test():
        hd.predict_bean(180)
    execution_time = timeit.timeit(do_test, number=100)
    print(f"执行总的时间: {execution_time * 1000} ms")
    # total time is 17.9ms on my computer in 100 times


if __name__ == '__main__':
    # from module.config.config import Config
    # from module.device.device import Device
    #
    # c = Config('oas1')
    # d = Device(c)
    # hd = HyaSlave(c, d)
    # covert_rgb()
    # test_predict_res()
    test_predict_bean()

