import cv2

from cached_property import cached_property
from pathlib import Path
from enum import Enum

from module.logger import logger
from module.base.timer import Timer
from module.atom.image import RuleImage
from module.exception import RequestHumanTakeover
from tasks.Hyakkiyakou.slave.hya_device import HyaDevice
from tasks.Hyakkiyakou.slave.hya_color import HyaColor
from tasks.Hyakkiyakou.assets import HyakkiyakouAssets


class HyaBuff(int, Enum):
    BUFF_STATE0 = -1  # None
    BUFF_STATE2 = 0  # 式神减速
    BUFF_STATE3 = 1  # 砸豆加速
    BUFF_STATE5 = 2  # 式神冰冻
    BUFF_STATE6 = 3  # 概率UP
    BUFF_STATE7 = 4  # 好友UP

    @classmethod
    def from_index(cls, index: int):
        for member in cls:
            if member.value == index:
                return member
        raise ValueError(f"No HyaBuff member with value {index}")



class HyaSlave(HyaDevice, HyaColor, HyakkiyakouAssets):
    """
    主要是用来跟游戏进行交互的
    """
    # x, y, w, h
    HUNDRED0HUNDRED: list[int] = [117, 647, 18, 25]
    DECADE0HUNDRED: list[int] = [131, 647, 18, 25]
    UNIT0HUNDRED: list[int] = [146, 647, 18, 25]
    DECADE0DECADE: list[int] = [126, 647, 18, 25]
    UNIT0DECADE: list[int] = [140, 647, 18, 25]
    UNIT0: list[int] = [132, 647, 18, 25]
    # buff
    BUFF_ROI1: list[int] = [150, 1, 150, 50]
    BUFF_ROI2: list[int] = [320, 1, 140, 50]
    BUFF_ROI3: list[int] = [840, 1, 150, 50]
    BUFF_ROI4: list[int] = [1100, 1, 140, 50]

    # 剩余豆子数量， 剩余式神数量， 一次砸豆子的数量， 第一个格子， 第二个格子， 第三个格子， 第四个格子
    slave_state: tuple = [250, 36, 10,
                          HyaBuff.BUFF_STATE0, HyaBuff.BUFF_STATE0, HyaBuff.BUFF_STATE0, HyaBuff.BUFF_STATE0]

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

    @cached_property
    def buff_state_rois(self) -> list[list[int]]:
        return [
            self.BUFF_ROI1,
            self.BUFF_ROI2,
            self.BUFF_ROI3,
            self.BUFF_ROI4
        ]

    @cached_property
    def buff_state_images(self) -> list[RuleImage]:
        return [
            self.I_HYA_STATE_BUFF02,  # 式神减速
            self.I_HYA_STATE_BUFF03,  # 砸豆加速
            self.I_HYA_STATE_BUFF05,  # 冰冻
            self.I_HYA_STATE_BUFF06,  # 概率up
            self.I_HYA_STATE_BUFF07,  # 好友UP
        ]

    def predict_res(self, current: int) -> int:
        for i in range(current, current-5, -1):
            unit = i % 10
            unit_img = self.res_r[unit] if i >= 10 else self.res_f[unit]
            if not self.appear(unit_img):
                continue
            if i < 10:
                return i
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

            elif bean >= 10:
                decade = bean // 10
                decade_img = self.bean[decade]
                decade_img.roi_back = self.DECADE0DECADE
                if not self.appear(decade_img):
                    continue
                unit = bean % 10
                unit_img = self.bean[unit]
                unit_img.roi_back = self.UNIT0DECADE
                if self.appear(unit_img):
                    return bean
                for i in range(10):
                    unit_img = self.bean[i]
                    unit_img.roi_back = self.UNIT0DECADE
                    if self.appear(unit_img):
                        return max(0, (bean // 10) * 10 + i)
            else:
                unit = bean % 10
                unit_img = self.bean[unit]
                unit_img.roi_back = self.UNIT0
                if self.appear(unit_img):
                    return bean
                for i in range(10):
                    unit_img = self.bean[i]
                    unit_img.roi_back = self.UNIT0
                    if self.appear(unit_img):
                        return max(0, i)
        # 最坏的情况下用ocr
        num = self.O_BEAN_NUMBER.ocr(self.device.image)
        if isinstance(num, int) and num >= 0:
            return num

        logger.warning(f'Cannot predict bean, current: {current}')
        return current

    def predict_buff_state(self, pos: int, current: HyaBuff = None) -> HyaBuff:
        color = self.buff_colors[pos]
        if self.match_color(color):
            return HyaBuff.BUFF_STATE0
        roi = self.buff_state_rois[pos]
        if current is not None and current != HyaBuff.BUFF_STATE0:
            current_image = self.buff_state_images[current]
            current_image.roi_back = roi
            if self.appear(current_image):
                return current
        for i, img in enumerate(self.buff_state_images):
            img.roi_back = roi
            if self.appear(img):
                # int to HyaBuff
                return HyaBuff.from_index(i)
        return HyaBuff.BUFF_STATE0

    def recognize_bean_05(self) -> bool:
        return self.appear(self.I_BEAN05)

    def recognize_bean_10(self) -> bool:
        return self.appear(self.I_BEAN10)

    def bean_05to10(self):
        self.swipe(self.S_BEAN_05TO10)

    def bean_10to05(self):
        self.swipe(self.S_BEAN_10TO05)

    # main process
    # ------------------------------------------------------------------------------------------------------------------

    def invite_friend(self, same: bool = True):
        logger.hr('Invite friend', 2)
        while 1:
            self.screenshot()
            if self.appear(self.I_FRIEND_SAME_1) or self.appear(self.I_FRIEND_SAME_2):
                break
            if self.appear_then_click(self.I_HINVITE, interval=4):
                continue
        if not self._invite_friend(True):
            if not self._invite_friend(False):
                raise RequestHumanTakeover('Invite friend failed')



    def _invite_friend(self, same: bool = True) -> bool:
        if not same:
            logger.info('Invite different server friend')
            self.ui_click(self.I_FRIEND_REMOTE_1, self.I_FRIEND_REMOTE_2)
        invite_timer = Timer(8)
        invite_timer.start()
        while 1:
            self.screenshot()
            if not self.appear(self.I_HINVITE):
                break
            if self.click(self.C_FRIEND_1, interval=2):
                continue
            if self.click(self.C_FRIEND_2, interval=3):
                continue
            if invite_timer.reached():
                logger.warning('Invite friend timeout, It may be no friend available')
                return False
        logger.info('Invite friend done')
        return True

    def update_state(self):
        res_bean = self.predict_bean(self.slave_state[0])
        res_shi = self.predict_res(self.slave_state[1])
        num_bean = 5 if self.recognize_bean_05() else 10
        buff_0 = self.predict_buff_state(pos=0, current=self.slave_state[3])
        buff_1 = self.predict_buff_state(pos=1, current=self.slave_state[4])
        buff_2 = self.predict_buff_state(pos=2, current=self.slave_state[5])
        buff_3 = self.predict_buff_state(pos=3, current=self.slave_state[6])
        self.slave_state = [
            res_bean, res_shi, num_bean, buff_0, buff_1, buff_2, buff_3
        ]
        return self.slave_state

    def reset_state(self):
        self.slave_state = [250, 36, 10,
                          HyaBuff.BUFF_STATE0, HyaBuff.BUFF_STATE0, HyaBuff.BUFF_STATE0, HyaBuff.BUFF_STATE0]
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
    img = cv2.imread('D:/Project/OnmyojiAutoScript/tasks/Hyakkiyakou/temp/20240621T221325/all1718979259551.png')
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    hd.device.image = img
    print(hd.predict_res(2))

    # def do_test():
    #     hd.predict_res(18)
    # execution_time = timeit.timeit(do_test, number=100)
    # print(f"执行总的时间: {execution_time * 1000} ms")
    # total time is 36.2ms on my computer /cpu:AMD Ryzen 5 3550H with Radeon Vega Mobile
    # 0.362ms per predict_res

def test_predict_bean():
    import timeit
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    hd = HyaSlave(c, d)
    img = cv2.imread('./tasks/Hyakkiyakou/temp/20240621T221325/all1718979269677.png')
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    hd.device.image = img
    print(hd.predict_bean(15))
    # def do_test():
    #     hd.predict_bean(180)
    # execution_time = timeit.timeit(do_test, number=100)
    # print(f"执行总的时间: {execution_time * 1000} ms")
    # total time is 17.9ms on my computer in 100 times

def test_predict_buff():
    import timeit
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    hd = HyaSlave(c, d)
    img = cv2.imread(r'E:\Project\OnmyojiAutoScript\tasks\Hyakkiyakou\temp\save14\all1718372600237.png')
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    hd.device.image = img
    print(hd.predict_buff_state(1))


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    hd = HyaSlave(c, d)
    # hd.invite_friend(False)

    # test_predict_res()
    test_predict_bean()
    # test_predict_buff()

