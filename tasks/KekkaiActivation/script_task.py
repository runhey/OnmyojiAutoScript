# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

import random
import re
from cached_property import cached_property
from datetime import datetime, timedelta
from module.atom.click import RuleClick

from module.base.timer import Timer
from module.atom.image_grid import ImageGrid
from module.atom.image import RuleImage
from module.base.utils import point2str
from module.logger import logger
from module.exception import TaskEnd, GameStuckError

from tasks.KekkaiUtilize.script_task import ScriptTask as KU
from tasks.KekkaiUtilize.utils import CardClass
from tasks.KekkaiActivation.assets import KekkaiActivationAssets
from tasks.KekkaiActivation.utils import parse_rule
from tasks.KekkaiActivation.config import ActivationConfig
from tasks.Utils.config_enum import ShikigamiClass
from tasks.GameUi.page import page_main, page_guild
from tasks.KekkaiActivation.config import CardType

""" 结界挂卡 """
class ScriptTask(KU, KekkaiActivationAssets):

    def run(self):
        con = self.config.kekkai_activation.activation_config
        self.ui_get_current_page()
        self.ui_goto(page_guild)

        # 在寮的主界面 检查是否有收取体力或者是收取寮资金
        # self.check_guild_ap_or_assets()

        # 进入寮结界
        self.goto_realm()

        if con.exchange_before:
            self.check_max_lv(con.shikigami_class)
        # 收取经验
        self.harvest_card()
        # 开始挂卡
        self.run_activation(con)
        while 1:
            # 关闭到结界界面
            self.screenshot()
            if self.appear(self.I_REALM_SHIN):
                break
            if self.appear(self.I_SHI_GROWN):
                break
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1):
                continue

        if con.exchange_max:
            self.check_max_lv(con.shikigami_class)
        # self.back_guild()
        self.ui_get_current_page()
        self.ui_goto(page_main)

        raise TaskEnd('KekkaiActivation')

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
    def order_targets(self) -> ImageGrid:
        rule = self.config.kekkai_activation.activation_config.card_type
        if rule == CardType.TAIKO:
            return ImageGrid([self.I_CARDS_KAIKO_6, self.I_CARDS_KAIKO_5])
        elif rule == CardType.FISH:
            return ImageGrid([self.I_CARDS_FISH_6, self.I_CARDS_FISH_5])
        else:
            logger.error('Unknown utilize rule')
            raise ValueError('Unknown utilize rule')

    def run_activation(self, _config: ActivationConfig) -> bool:
        """
        执行挂卡，要求在结界的界面
        顺便把下一次执行也设置了
        :return: 挂卡成功（）返回True，失败(时间没到提前来了)返回False
        退出的时候还是在挂卡界面而不是结界界面
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
                if self.appear(self.I_A_ACTIVATE_YELLOW, threshold=0.95):
                    continue
                if self.appear(self.I_A_DEMOUNT):
                    # 现在在动画里面
                    logger.info('Now in the animation')
                    logger.info('Now there is no card')
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
                    if self.appear(self.I_A_INVITE, threshold=0.8):
                        logger.info('Card is activated')
                        break
                    if self.appear_then_click(self.I_UI_CONFIRM, interval=0.6):
                        continue
                    if self.appear_then_click(self.I_A_ACTIVATE_YELLOW, interval=1):
                        continue
                interval = self.ocr_time(True)
                self.set_next_run("KekkaiActivation", success=True, finish=True, target=interval + datetime.now())
                return True
            # 如果是什么都没有，那就是可以开始挂卡了
            if not card_status and not card_effect:
                logger.info('Card is not selected also not using')
                self.screening_card(_config.card_type)

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

    def ocr_time(self, screenshot=False) -> timedelta or None:
        if screenshot:
            self.screenshot()
        delta = self.O_CARD_ALL_TIME.ocr_duration(self.device.image)
        if not isinstance(delta, timedelta):
            logger.warning('OCR error')
            return None
        if delta == timedelta(0):
            logger.error('The remaining time detected for this card is 0')
            logger.error('This may be due to the fact that the card has not yet been collected')
            raise GameStuckError
        return delta

    def screening_card(self, rule: str):
        """
        开始挑选卡
        :return:
        """

        if rule == CardType.TAIKO:
            card_class = CardClass.TAIKO
            target_class = self.I_A_CARD_KAIKO
        elif rule == CardType.FISH:
            card_class = CardClass.FISH
            target_class = self.I_A_CARD_FISH
        else:
            logger.warning('Unknown card rule')
            self.push_notify(content='Unknown card rule')
            return

        while 1:
            self.screenshot()

            if self.appear(target_class):
                time.sleep(0.3)
                self.screenshot()
                if self.appear(target_class):
                    break
            if self.click(self.C_A_SELECT_CARD_LIST, interval=2.5):
                continue
        logger.info('Appear card class: {}'.format(card_class))
        while 1:
            self.screenshot()
            if not self.appear(target_class):
                break
            if self.appear_then_click(target_class, interval=1):
                continue
        logger.info('Selected card class: {}'.format(card_class))

        # 找最优卡
        while 1:
            self.screenshot()
            target = self.check_card_num()
            if target is None:
                # 未发现卡，处理逻辑
                self._card_not_found()
            if self.appear(self.I_A_EMPTY):
                while 1:
                    self.screenshot()
                    if not self.appear(self.I_A_EMPTY):
                        self.config.kekkai_activation.activation_config.card_not_found_count = 0
                        self.config.save()
                        message = f'✅ 确认挂卡: {rule}'
                        self.save_image(content=message, push_flag=False, wait_time=0)
                        return
                    if self.click(target, interval=1):
                        continue

    def check_card_num(self):
        rule = self.config.kekkai_activation.activation_config.card_type
        if rule == CardType.TAIKO:
            min_card_num = self.config.kekkai_activation.activation_config.min_taiko_num
            check_card = "勾玉"
        elif rule == CardType.FISH:
            min_card_num = self.config.kekkai_activation.activation_config.min_fish_num
            check_card = "体力"
        else:
            logger.error('Unknown utilize rule')
            raise ValueError('Unknown utilize rule')

        ocr_count = 0
        while 1:
            self.screenshot()
            results = self.O_CHECK_CARD_NUMBER.detect_and_ocr(self.device.image)
            ocr_count += 1
            # 第一步：筛选出包含 "体力或者勾玉" 的结果
            filtered_results = [result for result in results if check_card in result.ocr_text]
            logger.info(f"识别到卡: {[result.ocr_text for result in filtered_results]}")

            # 第二步：提取数字并按数字排序
            numeric_results = []
            for result in filtered_results:
                # 使用正则表达式提取所有数字
                numbers = [int(num) for num in re.findall(r'\d+', result.ocr_text)]
                if numbers:  # 如果提取到数字
                    if numbers[0] < min_card_num:
                        continue
                    numeric_results.append((numbers[0], result))  # 按第一个数字排序

            if numeric_results:
                # 按数字大到小排序
                sorted_results = [result for _, result in sorted(numeric_results, key=lambda x: x[0], reverse=True)]
                max_result = sorted_results[0]  # 获取数字最大的结果对象

                box = max_result.box  # 获取边界框坐标
                x_min = self.O_CHECK_CARD_NUMBER.roi[0] + box[0][0]
                y_min = self.O_CHECK_CARD_NUMBER.roi[1] + box[0][1]
                width = box[1][0] - box[0][0]
                height = box[2][1] - box[1][1]
                roi = int(x_min), int(y_min), int(width), int(height)

                target = RuleClick(roi_front=roi, roi_back=roi, name="tmpclick")
                logger.info(f"选择挂卡: [{max_result.ocr_text}] {roi}")

                return target
            else:
                if ocr_count > 3:
                    logger.error('多次未找到符合条件的结果, 退出')
                    return None
                logger.warning("未找到符合条件的结果, 准备往上滑动")
                duration = 2
                safe_pos_x = random.randint(200, 400)
                safe_pos_y = random.randint(580, 600)
                p1 = (safe_pos_x, safe_pos_y)
                p2 = (safe_pos_x, safe_pos_y - 410)
                logger.info('Swipe %s -> %s, %sS ' % (point2str(*p1), point2str(*p2), duration))
                self.device.swipe_adb(p1, p2, duration=duration)
                time.sleep(1)
                continue

    def _card_not_found(self):
        # 获取配置引用
        activation_config = self.config.kekkai_activation.activation_config
        # 多少分钟后重试
        retry_minutes = 180
        retry_count = 3
        # 递增未找到卡的计数器
        activation_config.card_not_found_count += 1

        if activation_config.card_not_found_count >= retry_count:
            # 达到重试上限时的处理
            log_msg = f"⚠️{activation_config.card_type}卡未检出（累计{retry_count}次），{retry_minutes}分钟后重试"
            activation_config.card_not_found_count = 0  # 重置计数器并延长下次执行时间
            next_run = datetime.now() + timedelta(minutes=retry_minutes)
        else:
            # # 未达上限切换卡类型
            new_type = (
                CardType.FISH
                if activation_config.card_type == CardType.TAIKO
                else CardType.TAIKO
            )
            log_msg = f"🔄{activation_config.card_type}卡未检出 → 切换{new_type}"
            activation_config.card_type = new_type
            next_run = datetime.now()

        # 统一记录日志和推送
        self.save_image(content=log_msg, push_flag=True)

        # 保存配置并设置下次执行
        self.config.save()
        self.set_next_run("KekkaiActivation", success=True, finish=True, target=next_run)
        raise TaskEnd

    def check_max_lv(self, shikigami_class: ShikigamiClass = ShikigamiClass.N):
        """
        在结界界面，进入式神育成，检查是否有满级的，如果有就换下一个
        退出的时候还是结界界面
        :return:
        """
        self.realm_goto_grown()
        if self.appear(self.I_RS_LEVEL_MAX):
            # 存在满级的式神
            logger.info('Exist max level shikigami and replace it')
            self.unset_shikigami_max_lv()
            self.switch_shikigami_class(shikigami_class)
            self.set_shikigami(shikigami_order=7, stop_image=self.I_RS_NO_ADD)
        else:
            logger.info('No max level shikigami')
        if self.detect_no_shikigami():
            logger.warning('There are no any shikigami grow room')
            self.switch_shikigami_class(shikigami_class)
            self.set_shikigami(shikigami_order=7, stop_image=self.I_RS_NO_ADD)

        # 回到结界界面
        while 1:
            self.screenshot()

            if self.appear(self.I_REALM_SHIN) and self.appear(self.I_SHI_GROWN):
                self.screenshot()
                if not self.appear(self.I_REALM_SHIN):
                    continue
                break
            if self.appear_then_click(self.I_UI_BACK_BLUE, interval=2.5):
                continue

    def harvest_card(self):
        """
        收卡的经验
        :return:
        """
        self.appear_then_click(self.I_A_HARVEST_EXP)  # 如果到最后没有领的话有下面的一些图片
        self.appear_then_click(self.I_A_HARVEST_FISH4)  # 斗鱼4/5区别不大 斗鱼的如果一直没有领的话
        self.appear_then_click(self.I_A_HARVEST_KAIKO_4)  # 太鼓4
        self.appear_then_click(self.I_A_HARVEST_KAIKO_3)  # 太鼓3
        self.appear_then_click(self.I_A_HARVEST_KAIKO_6)  # 太鼓6
        self.appear_then_click(self.I_A_HARVEST_FISH_6)  # 斗鱼6
        self.appear_then_click(self.I_A_HARVEST_MOON_3)  # 太阴3
        self.appear_then_click(self.I_A_HARVEST_FISH_3)  # 斗鱼三


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device
    import cv2

    c = Config('switch')
    d = Device(c)

    t = ScriptTask(c, d)
    t.check_card_num()
    # t.run_activation(t.config.kekkai_activation.activation_config)
