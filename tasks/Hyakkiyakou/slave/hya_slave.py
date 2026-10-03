import time

import cv2

from difflib import SequenceMatcher

from cached_property import cached_property
from pathlib import Path
from enum import Enum

from module.logger import logger
from module.base.timer import Timer
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr
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

    # 邀请面板好友列表左右两列的名字文字区域（避开头像和等级数字，防止数字混入导致匹配失败）
    O_HYA_FRIEND_NAME_L = RuleOcr(roi=(450, 215, 182, 345), area=(450, 215, 182, 345),
                                  mode='Full', method='Default', keyword='', name='hya_friend_name_l')
    O_HYA_FRIEND_NAME_R = RuleOcr(roi=(725, 215, 178, 345), area=(725, 215, 178, 345),
                                  mode='Full', method='Default', keyword='', name='hya_friend_name_r')
    # 召回活动面板整体左移，名字区域随之偏移
    O_HYA_FRIEND_NAME_L_RECALL = RuleOcr(roi=(238, 215, 182, 345), area=(238, 215, 182, 345),
                                         mode='Full', method='Default', keyword='', name='hya_friend_name_l_recall')
    O_HYA_FRIEND_NAME_R_RECALL = RuleOcr(roi=(516, 215, 178, 345), area=(516, 215, 178, 345),
                                         mode='Full', method='Default', keyword='', name='hya_friend_name_r_recall')
    # 好友被邀请次数达到今日上限的提示
    O_HYA_INVITE_LIMIT = RuleOcr(roi=(385, 235, 520, 62), area=(385, 235, 520, 62),
                                 mode='Full', method='Default', keyword='上限', name='hya_invite_limit')

    def invite_friend(self, friend_name: str = ''):
        logger.hr('Invite friend', 2)
        self.ui_click(self.I_HINVITE, self.I_CHECK_INVITATION, interval=4)
        logger.info('Entry check invitation')

        # 是否有召回活动(星重聚阴阳师)
        if self.appear(self.I_ENSURE_RECALL):
            hya_recall_activity = True
            # 应该动态改roi而不是新开一个图
            friend_buttons1 = [self.I_FRIEND_SAME_1_RECALL, self.I_FRIEND_REMOTE_1_RECALL, ]
            friend_buttons2 = [self.I_FRIEND_SAME_2_RECALL, self.I_FRIEND_REMOTE_2_RECALL, ]
        else:
            hya_recall_activity = False
            # 资产命名与页签文字相反：REMOTE 模板是"跨区"，RYOU 模板是"寮友"
            # 必须按面板实际位置排：好友(SAME) / 寮友(RYOU) / 跨区(REMOTE)，否则点页签永远点不中
            friend_buttons1 = [self.I_FRIEND_SAME_1, self.I_FRIEND_RYOU_1, self.I_FRIEND_REMOTE_1]
            friend_buttons2 = [self.I_FRIEND_SAME_2, self.I_FRIEND_RYOU_2, self.I_FRIEND_REMOTE_2]

        # 优先邀请指定好友，失败则退回默认邀请
        if friend_name:
            logger.info(f'Invite specific friend: {friend_name}')
            if self._invite_specific_friend(friend_name, hya_recall_activity=hya_recall_activity):
                return True
            logger.warning('Invite specific friend failed, fallback to default invite')
            # 面板可能已关闭，重新进入
            self.screenshot()
            if not self.appear(self.I_CHECK_INVITATION):
                self.ui_click(self.I_HINVITE, self.I_CHECK_INVITATION, interval=4, timeout=10)

        # 依次邀请,
        self.friend_state = 0  # 不需要每一次都从0开始，可以固定一下
        while self.friend_state < 3:
            match self.friend_state:
                case 0:
                    logger.info('Invite same server friend')
                    # 指定好友查找失败后列表可能停在底部(全是灰名)，先重开面板回顶部再点第一个
                    if not self._invite_friend(button1=friend_buttons1[0], button2=friend_buttons2[0],
                                               hya_recall_activity=hya_recall_activity,
                                               reopen_panel=bool(friend_name)):
                        self.friend_state += 1
                    else:
                        return True
                case 1:
                    logger.info('Invite guild friend')
                    if not self._invite_friend(button1=friend_buttons1[1], button2=friend_buttons2[1],
                                               hya_recall_activity=hya_recall_activity,
                                               reopen_panel=bool(friend_name)):
                        self.friend_state += 1
                    else:
                        return True
                case 2:
                    logger.info('Invite remote friend')
                    if not self._invite_friend(button1=friend_buttons1[2], button2=friend_buttons2[2],
                                               hya_recall_activity=hya_recall_activity,
                                               reopen_panel=bool(friend_name)):
                        self.friend_state += 1
                    else:
                        return True
                case _:
                    raise RequestHumanTakeover('Invite friend failed')

    def _reopen_invite_panel(self):
        """
        粉叉关闭邀请面板再重新打开，让列表回到顶部。
        不用向上滑动：划到顶部会触发好友搜索框挡住列表，且滑动可能被游戏吞掉
        """
        logger.info('Reopen invite panel to reset friend list to top')
        self.ui_click(self.I_HCLOSE_RED, self.I_HINVITE, interval=1, timeout=10)
        self.ui_click(self.I_HINVITE, self.I_CHECK_INVITATION, interval=2, timeout=10)

    def _invite_friend(self, button1: RuleImage, button2: RuleImage, hya_recall_activity: bool = False,
                       reopen_panel: bool = False) -> bool:
        logger.info('Start clicking')
        self.ui_click(button1, button2, timeout=10)
        logger.info('End clicking')
        # 列表可能停在底部(全是最近受邀的灰名)，重开面板让列表回到顶部再点左上第一个好友
        if reopen_panel:
            self._reopen_invite_panel()
        invite_timer = Timer(8)
        invite_timer.start()
        while 1:
            self.screenshot()
            if not self.appear(self.I_HINVITE):
                break
            # 是否有召回活动
            if hya_recall_activity:
                if self.click(self.C_FRIEND_1_RECALL, interval=2):
                    continue
                if self.click(self.C_FRIEND_2_RECALL, interval=3):
                    continue
            else:
                if self.click(self.C_FRIEND_1, interval=2):
                    continue
                if self.click(self.C_FRIEND_2, interval=3):
                    continue
            if invite_timer.reached():
                logger.warning('Invite friend timeout, It may be no friend available')
                return False
        logger.info('Invite friend done')
        return True

    def _find_friend_click(self, rules: list[RuleOcr], friend_name: str) -> bool:
        """
        在左右两列OCR区域中查找好友名并点击。
        OCR对单个汉字可能误识(如"欧欧Yuumi"识别成"欠欧Yuumi")，因此精确匹配优先，
        否则取相似度最高且不低于0.8的候选；左右两列一起比较后再点击，避免模糊命中抢占精确命中
        :return: 是否找到并点击
        """
        target = friend_name.replace(' ', '')
        best = None  # (exact优先级, 相似度, x, y, 原文)
        for rule in rules:
            results = rule.detect_and_ocr(self.device.image)
            for result in results:
                text = (result.ocr_text or '').replace(' ', '')
                if not text:
                    continue
                box = result.box
                x = rule.roi[0] + (box[0, 0] + box[1, 0]) / 2
                y = rule.roi[1] + (box[0, 1] + box[2, 1]) / 2
                if target in text:
                    best = (1, 1.0, x, y, result.ocr_text)
                    break  # 精确命中，无需再看这一列的其他行
                ratio = SequenceMatcher(None, target, text).ratio()
                if ratio >= 0.8 and (best is None or (best[0] == 0 and ratio > best[1])):
                    best = (0, ratio, x, y, result.ocr_text)
            if best is not None and best[0] == 1:
                break  # 精确命中，不再扫描另一列
        if best is None:
            return False
        logger.info(f'Find friend {best[4]} (exact={bool(best[0])}, similarity {best[1]:.2f}), '
                    f'click ({int(best[2])}, {int(best[3])})')
        self._humanized_click_delay()
        self.device.click(x=int(best[2]), y=int(best[3]), control_name='hya_friend_name')
        return True

    def _wait_invite_result(self) -> bool:
        """
        点击好友后等待邀请结果
        :return: True 邀请成功(面板关闭且邀请好友按钮变为好友头像)；
                 False 达到今日邀请上限或超时(需要回退默认邀请)
        """
        timer = Timer(8)
        timer.start()
        while 1:
            self.screenshot()
            if not self.appear(self.I_HINVITE) and not self.appear(self.I_CHECK_INVITATION):
                logger.info('Invite specific friend done')
                return True
            if self.ocr_appear(self.O_HYA_INVITE_LIMIT):
                logger.warning('Friend invite limit reached today')
                return False
            if timer.reached():
                logger.warning('Invite specific friend result timeout')
                return False
            time.sleep(0.5)

    def _friend_list_names(self, rules: list[RuleOcr]) -> list[str]:
        """
        读取当前好友列表可见的名字(左右两列)，用于判断滑动是否真的翻页
        """
        names = []
        for rule in rules:
            results = rule.detect_and_ocr(self.device.image)
            for result in results:
                text = (result.ocr_text or '').replace(' ', '')
                if text:
                    names.append(text)
        return names

    def _scroll_friend_list(self, rules: list[RuleOcr], scroll_x: int, direction: int) -> bool:
        """
        滑动好友列表并确认是否真的翻页。
        游戏偶尔吞掉滑动(日志里 "Swipe x distance is 0")，此时列表没动，
        盲滑会一路翻到底部卡死，所以滑动前后对比OCR名字
        :param direction: 1 向下翻页; -1 向上翻页
        :return: True 列表内容发生了变化
        """
        before = self._friend_list_names(rules)
        if direction > 0:
            self.device.swipe(p1=(scroll_x, 550), p2=(scroll_x, 320), control_name='hya_friend_scroll')
        else:
            self.device.swipe(p1=(scroll_x, 320), p2=(scroll_x, 550), control_name='hya_friend_scroll')
        time.sleep(1)
        self.screenshot()
        after = self._friend_list_names(rules)
        return after != before

    def _invite_specific_friend(self, friend_name: str, hya_recall_activity: bool = False) -> bool:
        """
        在好友/寮友/跨区页签中查找指定好友并邀请，列表支持向下滑动
        :return: True 邀请成功; False 失败(未找到/达到上限)，需要回退默认邀请
        """
        if hya_recall_activity:
            rules = [self.O_HYA_FRIEND_NAME_L_RECALL, self.O_HYA_FRIEND_NAME_R_RECALL]
            tabs = [(self.I_FRIEND_SAME_1_RECALL, self.I_FRIEND_SAME_2_RECALL),
                    (self.I_FRIEND_REMOTE_1_RECALL, self.I_FRIEND_REMOTE_2_RECALL)]
            scroll_x = 470
        else:
            rules = [self.O_HYA_FRIEND_NAME_L, self.O_HYA_FRIEND_NAME_R]
            # 资产命名与页签文字相反：REMOTE 模板是"跨区"，RYOU 模板是"寮友"
            # 按面板实际位置依次切换：好友 / 寮友 / 跨区
            tabs = [(self.I_FRIEND_SAME_1, self.I_FRIEND_SAME_2),
                    (self.I_FRIEND_RYOU_1, self.I_FRIEND_RYOU_2),
                    (self.I_FRIEND_REMOTE_1, self.I_FRIEND_REMOTE_2)]
            scroll_x = 620
        for tab_off, tab_on in tabs:
            # 超时兜底：页签模板失配时跳过该页签而不是无限等待触发卡死重启
            self.ui_click(tab_off, tab_on, interval=1, timeout=10)
            time.sleep(1.5)  # 等待好友列表加载完成
            for _ in range(8):  # 每个页签最多向下滑动8次(滑动被吞掉的不计入翻页)
                self.screenshot()
                if self._find_friend_click(rules, friend_name):
                    return self._wait_invite_result()
                # 当前屏幕没有该好友，向下滑动列表继续找；滑动没生效就重试
                if not self._scroll_friend_list(rules, scroll_x, direction=1):
                    logger.info('Friend list scroll has no effect, reached bottom or swipe ignored')
                    break
        logger.warning(f'Not find friend {friend_name} in all tabs')
        return False

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

