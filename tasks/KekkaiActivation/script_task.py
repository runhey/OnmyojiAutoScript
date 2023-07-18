# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from cached_property import cached_property
from datetime import datetime, timedelta

from module.base.timer import Timer
from module.atom.image_grid import ImageGrid
from module.atom.image import RuleImage
from module.logger import logger
from module.exception import TaskEnd

from tasks.KekkaiUtilize.script_task import ScriptTask as KU
from tasks.KekkaiUtilize.utils import CardClass
from tasks.KekkaiActivation.assets import KekkaiActivationAssets
from tasks.KekkaiActivation.utils import parse_rule
from tasks.KekkaiActivation.config import ActivationConfig


class ScriptTask(KU, KekkaiActivationAssets):

    def run(self):
        pass

    @cached_property
    def dict_card_image(self) -> dict:
        match_targets = {
            CardClass.TAIKO6: self.I_CARDS_KAIKO_6,
            CardClass.TAIKO5: self.I_CARDS_KAIKO_5,
            CardClass.TAIKO4: self.I_CARDS_KAIKO_4,
            CardClass.TAIKO3: self.I_CARDS_KAIKO_3,
            CardClass.FISH6: self.I_CARDS_FISH_6,
            CardClass.FISH5: self.I_CARDS_FISH_5,
            CardClass.FISH4: self.I_CARDS_FISH_4,
            CardClass.FISH3: self.I_CARDS_FISH_3,
            CardClass.MOON6: self.I_CARDS_MOON_6,
            CardClass.MOON5: self.I_CARDS_MOON_5,
            CardClass.MOON4: self.I_CARDS_MOON_4,
            CardClass.MOON3: self.I_CARDS_MOON_3,
            CardClass.MOON2: self.I_CARDS_MOON_2,
            CardClass.MOON1: self.I_CARDS_MOON_1
        }
        return match_targets

    @cached_property
    def dict_image_card(self) -> dict:
        return {v: k for k, v in self.dict_card_image.items()}

    @cached_property
    def order_cards(self) -> list[CardClass]:
        # 重写
        config = self.config.kekkai_activation.activation_config.card_rule
        return parse_rule(config)

    @cached_property
    def order_targets(self) -> ImageGrid:
        # 重写
        return ImageGrid([self.dict_card_image[card] for card in self.order_cards])

    def run_activation(self, _config: ActivationConfig) -> bool:
        """
        执行挂卡，要求在结界的界面
        顺便把下一次执行也设置了
        :return: 挂卡成功（）返回True，失败(时间没到提前来了)返回False
        """
        self.goto_cards()
        # 太诡异了 为什么有这么长的动画, 那么长的动画先休息一会
        logger.hr('Start activation')
        time.sleep(0.5)
        while 1:
            self.screenshot()
            card_status = self.check_card_status()
            card_effect = self.check_card_effect()

            # 不稳定太，等待动画结束
            if not card_status and not card_effect:
                # 黄色的 ”激活“
                if self.appear(self.I_A_ACTIVATE_YELLOW, threshold=0.99):
                    continue
            # 如果这张卡生效着，在使用中
            if card_status and card_effect:
                logger.info('Card is using')
                interval = self.ocr_time()
                self.set_next_run("KekkaiActivation", success=False, finish=True, target=interval+datetime.now())
                return False
            # 如果已经选中这张卡了， 那就激活这张卡
            if card_status and not card_effect:
                logger.info('Card is selected but not using')
                while 1:
                    self.screenshot()
                    if self.appear(self.I_A_INVITE):
                        logger.info('Card is activated')
                        break
                    # if self.appear_then_click(self.I_UI_CONFIRM, interval=0.6):
                    #     continue
                    # if self.appear_then_click(self.I_A_ACTIVATE_YELLOW, interval=1):
                    #     continue
                interval = self.ocr_time(True)
                self.set_next_run("KekkaiActivation", success=True, finish=True, target=interval + datetime.now())
                break
            # 如果是什么都没有，那就是可以开始挂卡了
            if not card_status and not card_effect:
                logger.info('Card is not selected also not using')
                self.screening_card(_config.card_rule)






    def goto_cards(self):
        """
        寮结界,前往挂卡界面
        :return:
        """
        while 1:
            self.screenshot()

            if self.appear(self.I_A_CHECK_CARD):
                break
            if self.appear(self.I_A_AUTO_INVITE):
                break
            if self.appear_then_click(self.I_SHI_CARD, interval=1):
                continue
        logger.info('Enter card page')

    def check_card_status(self, screenshot=False) -> bool:
        """
        判断使用有挂卡在上面了， 判断依据就是如果没看就可以显示背景图
        :param screenshot:
        :return: 如果有卡在上面了返回True，否则返回False
        """
        if screenshot:
            self.screenshot()
        return not self.appear(self.I_A_EMPTY)

    def check_card_effect(self, screenshot=False) -> bool:
        """
        检查这张卡是否生效了, 如果是出现的“邀请”那就是生效了， 如果是“激活”那就是还没生效
        :param screenshot:
        :return: 生效返回True
        """
        if screenshot:
            self.screenshot()
        if self.appear(self.I_A_INVITE, threshold=0.8):
            return True
        elif self.appear(self.I_A_ACTIVATE_YELLOW):
            return False
        logger.info('Unknown card effect')
        while 1:
            self.screenshot()
            if self.appear(self.I_A_INVITE, threshold=0.7):
                return True
            elif self.appear(self.I_A_ACTIVATE_YELLOW):
                return False
            elif self.appear(self.I_A_ACTIVATE_GRAY):
                return False
        return False

    def ocr_time(self, screenshot=False) -> timedelta or None:
        if screenshot:
            self.screenshot()
        delta = self.O_CARD_ALL_TIME.ocr_duration(self.device.image)
        if not isinstance(delta, timedelta):
            logger.warning('OCR error')
            return None
        return delta

    def screening_card(self, rule: str):
        """
        开始挑选卡
        :return:
        """

        def run_auto():
            while 1:
                self.screenshot()
                if not self.appear(self.I_A_EMPTY) and self.appear(self.I_A_ACTIVATE_YELLOW, threshold=0.9):
                    break
                if self.click(self.C_A_SELECT_AUTO, interval=1):
                    continue

        if rule == "auto":
            logger.info('Auto select card')
            run_auto()
            return

        card_class = None
        target_class = None
        top_card = self.order_cards[0]
        if top_card.startswith(CardClass.TAIKO):  # 太鼓
            card_class = CardClass.TAIKO
            target_class = self.I_A_CARD_KAIKO
        elif top_card.startswith(CardClass.MOON):  # 太阴
            card_class = CardClass.MOON
            target_class = self.I_A_CARD_MOON
        elif top_card.startswith(CardClass.FISH):  # 斗鱼
            card_class = CardClass.FISH
            target_class = self.I_A_CARD_FISH

        if card_class is None:
            logger.warning('Unknown card class')
            run_auto()
            return

        while 1:
            self.screenshot()

            if self.appear(target_class):
                time.sleep(0.3)
                self.screenshot()
                if self.appear(target_class):
                    break
            if self.click(self.C_A_SELECT_CARD_LIST, interval=1):
                continue
        logger.info('Appear card class: {}'.format(card_class))
        while 1:
            self.screenshot()
            if not self.appear(target_class):
                break
            if self.appear_then_click(target_class, interval=1):
                continue
        logger.info('Selected card class: {}'.format(card_class))

        # 得了开始一直往下滑动 找最优卡
        card_best = None
        swipe_count = 0
        while 1:
            self.screenshot()
            current_best = self._current_select_best(card_best)
            if current_best is None:
                break

            if current_best == self.order_cards[0]:
                break
            # 为什么找到第二个最优解也是会退出呢？？？
            # 这个是因为一般是从高星到低星来找， 基本上第二个最优解就是最优解了
            elif current_best == self.order_cards[1]:
                break

            # 超过十次就退出
            if swipe_count > 20:
                logger.warning('Swipe count is more than 10')
                break
            # 一直向下滑动
            self.swipe(self.S_CARDS_SWIPE, interval=0.9)
            swipe_count += 1
            time.sleep(3)

    def _image_convert_card(self, target: RuleImage) -> CardClass:
        """
        就是把一张图转化 到某个具体的类
        :return:
        """
        try:
            return self.dict_image_card[target]
        except KeyError:
            logger.warning(f'Unknown card class: {target}')
            return CardClass.UNKNOWN

    def _current_select_best(self, last_best: CardClass or None) -> CardClass | None:
        self.screenshot()
        target = self.order_targets.find_anyone(self.device.image)
        if target is None:
            logger.info('No target card found')
            return None
        current_card = self._image_convert_card(target)
        if current_card == CardClass.UNKNOWN:
            logger.info('Unknown card class')
            return None
        logger.info(f'Current best card class: {current_card}')

        # 如果当前的最好的卡，不比上一次最好的卡，那就退出
        if last_best is not None:
            last_index = self.order_cards.index(last_best)
            current_index = self.order_cards.index(current_card)
            if current_index > last_index:
                # 不比上一张卡好就退出不执行操作
                logger.info('Current card is not better than last best card')
                return last_best

        # 否则就是比上一张卡好，那就执行操作 点击操作
        logger.info('Current select card: %s', current_card)
        # 如果一开始是没有选择中的，那就稳定点否则就是只管点击
        self.screenshot()
        if self.appear(self.I_A_EMPTY):
            while 1:
                self.screenshot()
                if not self.appear(self.I_A_EMPTY):
                    return current_card
                if self.appear_then_click(target, interval=1):
                    continue
        self.appear_then_click(target, interval=0.5)
        return current_card


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device
    import cv2

    c = Config('oas1')
    d = Device(c)

    t = ScriptTask(c, d)
    # t.swipe(t.S_CARDS_SWIPE, interval=0.9)
    t.run_activation(t.config.kekkai_activation.activation_config)
