# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import numpy as np

from time import sleep
from datetime import datetime, timedelta, time
from typing import Union

from module.config.utils import convert_to_underscore
from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.long_click import RuleLongClick
from module.atom.swipe import RuleSwipe
from module.atom.ocr import RuleOcr
from module.atom.list import RuleList
from module.ocr.base_ocr import OcrMode, OcrMethod
from module.logger import logger
from module.base.timer import Timer
from module.config.config import Config
from module.config.utils import get_server_next_update, nearest_future, dict_to_kv, parse_tomorrow_server
from module.device.device import Device
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.GlobalGame.config_emergency import FriendInvitation, WhenNetworkAbnormal, WhenNetworkError
from tasks.Component.Costume.costume_base import CostumeBase

from module.exception import GameStuckError, ScriptError


class BaseTask(GlobalGameAssets, CostumeBase):
    config: Config = None
    device: Device = None

    folder: str
    name: str
    stage: str

    limit_time: timedelta = None  # 限制运行的时间，是软时间，不是硬时间
    limit_count: int = None  # 限制运行的次数
    current_count: int = None  # 当前运行的次数

    def __init__(self, config: Config, device: Device) -> None:
        """

        :rtype: object
        """
        self.config = config
        self.device = device

        self.interval_timer = {}  # 这个是用来记录每个匹配的运行间隔的，用于控制运行频率
        self.start_time = datetime.now()  # 启动的时间
        self.check_costume(self.config.global_game.costume_config)
        self.friend_timer = None  # 这个是用来记录勾协的时间的
        if self.config.global_game.emergency.invitation_detect_interval:
            self.interval_time = self.config.global_game.emergency.invitation_detect_interval
            self.friend_timer = Timer(self.interval_time)
            self.friend_timer.start()

        # 战斗次数相关
        self.current_count = 0  # 战斗次数

    def screenshot(self):
        """
        截图 引入中间函数的目的是 为了解决如协作的这类突发的事件
        :return:
        """
        self.device.screenshot()
        # 判断勾协
        if self.friend_timer and self.friend_timer.reached():
            self.friend_timer.reset()
            invite = self.appear(self.I_G_ACCEPT)
            detect_record = self.device.detect_record
            # 如果是全部接受
            if invite and self.config.global_game.emergency.friend_invitation == FriendInvitation.ACCEPT:
                # 如果是接受邀请
                logger.info(f"Accept friend invitation")
                while 1:
                    self.device.screenshot()
                    if self.appear_then_click(self.I_G_ACCEPT, interval=1):
                        continue
                    if not self.appear(self.I_G_ACCEPT):
                        break
            # 如果是全部拒绝
            elif invite and self.config.global_game.emergency.friend_invitation == FriendInvitation.REJECT:
                logger.info(f"Reject friend invitation")
                while 1:
                    self.device.screenshot()
                    if self.appear_then_click(self.I_G_REJECT, interval=1):
                        continue
                    if not self.appear(self.I_G_REJECT):
                        break
            # 最后一个是仅仅接受勾协
            elif invite and self.config.global_game.emergency.friend_invitation == FriendInvitation.ONLY_JADE:
                logger.info(f"Accept jade invitation")
                while 1:
                    self.device.screenshot()
                    if self.appear_then_click(self.I_G_ACCEPT, interval=1):
                        continue
                    if not self.appear(self.I_G_ACCEPT):
                        break
            # 有的时候长战斗 点击后会取消战斗状态
            self.device.detect_record = detect_record
            # 判断网络异常
            if self.appear(self.I_NETWORK_ABNORMAL):
                logger.warning(f"Network abnormal")
                raise GameStuckError

            # 判断网络错误
            if self.appear(self.I_NETWORK_ERROR):
                logger.warning(f"Network error")
                raise GameStuckError

        return self.device.image
        # 返回截图

    def appear(self, target: RuleImage, interval: float = None, threshold: float = None):
        """

        :param target: 匹配的目标可以是RuleImage, 也可以是RuleOcr
        :param interval:
        :param threshold:
        :return:
        """
        if not isinstance(target, RuleImage):
            return False

        if interval:
            if target.name in self.interval_timer:
                if self.interval_timer[target.name].limit != interval:
                    self.interval_timer[target.name] = Timer(interval)
            else:
                self.interval_timer[target.name] = Timer(interval)
            if not self.interval_timer[target.name].reached():
                return False

        appear = target.match(self.device.image, threshold=threshold)

        if appear and interval:
            self.interval_timer[target.name].reset()

        return appear

    def appear_then_click(self,
                          target: RuleImage,
                          action: Union[RuleClick, RuleLongClick] = None,
                          interval: float = None,
                          threshold: float = None,
                          duration: float = None):
        """
        出现了就点击，默认点击图片的位置，如果添加了click参数，就点击click的位置
        :param duration: 如果是长按，可以手动指定duration，不指定默认.单位是ms！！！！
        :param action: 可以是RuleClick, 也可以是RuleLongClick
        :param target: 可以是RuleImage后续支持RuleOcr
        :param interval:
        :param threshold:
        :return: True or False
        """
        if not isinstance(target, RuleImage):
            return False

        appear = self.appear(target, interval=interval, threshold=threshold)
        if appear and not action:
            x, y = target.coord()
            self.device.click(x, y, control_name=target.name)

        elif appear and action:
            x, y = action.coord()
            if isinstance(action, RuleLongClick):
                if duration is None:
                    self.device.long_click(x, y, duration=action.duration / 1000, control_name=target.name)
                else:
                    self.device.long_click(x, y, duration=duration / 1000, control_name=target.name)
            elif isinstance(action, RuleClick):
                self.device.click(x, y, control_name=target.name)

        return appear

    def wait_until_appear(self,
                          target: RuleImage,
                          skip_first_screenshot=False,
                          wait_time: int = None) -> bool:
        """
        等待直到出现目标
        :param wait_time: 等待时间，单位秒
        :param target:
        :param skip_first_screenshot:
        :return:
        """
        wait_timer = None
        if wait_time:
            wait_timer = Timer(wait_time)
            wait_timer.start()
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.screenshot()
            if wait_timer and wait_timer.reached():
                logger.warning(f"Wait until appear {target.name} timeout")
                return False
            if self.appear(target):
                return True

    def wait_until_appear_then_click(self,
                                     target: RuleImage,
                                     action: Union[RuleClick, RuleLongClick] = None) -> None:
        """
        等待直到出现目标，然后点击
        :param action:
        :param target:
        :return:
        """
        self.wait_until_appear(target)
        if action is None:
            self.device.click(target.coord(), control_name=target.name)
        elif isinstance(action, RuleLongClick):
            self.device.long_click(target.coord(), duration=action.duration / 1000, control_name=target.name)
        elif isinstance(action, RuleClick):
            self.device.click(target.coord(), control_name=target.name)

    def wait_until_disappear(self, target: RuleImage) -> None:
        while 1:
            self.screenshot()
            if not self.appear(target):
                break

    def wait_until_stable(self,
                          target: RuleImage,
                          timer=Timer(0.3, count=1),
                          timeout=Timer(5, count=10),
                          skip_first_screenshot=True):
        """
        等待目标稳定，即连续多次匹配成功
        :param target:
        :param timer:
        :param timeout:
        :param skip_first_screenshot:
        :return:
        """
        target._match_init = False
        timeout.reset()
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.screenshot()

            if target._match_init:
                if target.match(self.device.image):
                    if timer.reached():
                        break
                else:
                    # button.load_color(self.device.image)
                    timer.reset()
            else:
                # target.load_color(self.device.image)
                target._match_init = True

            if timeout.reached():
                logger.warning(f'Wait_until_stable({target}) timeout')
                break

    def swipe(self, swipe: RuleSwipe, interval: float = None) -> None:
        """

        :param interval:
        :param swipe:
        :return:
        """
        if not isinstance(swipe, RuleSwipe):
            return

        if interval:
            if swipe.name in self.interval_timer:
                # 如果传入的限制时间不一样，则替换限制新的传入的时间
                if self.interval_timer[swipe.name].limit != interval:
                    self.interval_timer[swipe.name] = Timer(interval)
            else:
                # 如果没有限制时间，则创建限制时间
                self.interval_timer[swipe.name] = Timer(interval)
            # 如果时间还没到达，则不执行
            if not self.interval_timer[swipe.name].reached():
                return

        x1, y1, x2, y2 = swipe.coord()
        self.device.swipe(p1=(x1, y1), p2=(x2, y2), control_name=swipe.name)

        # 执行后，如果有限制时间，则重置限制时间
        if interval:
            # logger.info(f'Swipe {swipe.name}')
            self.interval_timer[swipe.name].reset()

    def click(self, click: Union[RuleClick, RuleLongClick] = None, interval: float = None) -> bool:
        """
        点击或者长按
        :param interval:
        :param click:
        :return:
        """
        if not click:
            return False

        if interval:
            if click.name in self.interval_timer:
                # 如果传入的限制时间不一样，则替换限制新的传入的时间
                if self.interval_timer[click.name].limit != interval:
                    self.interval_timer[click.name] = Timer(interval)
            else:
                # 如果没有限制时间，则创建限制时间
                self.interval_timer[click.name] = Timer(interval)
            # 如果时间还没到达，则不执行
            if not self.interval_timer[click.name].reached():
                return False

        x, y = click.coord()
        if isinstance(click, RuleLongClick):
            self.device.long_click(x=x, y=y, duration=click.duration / 1000, control_name=click.name)
        elif isinstance(click, RuleClick) or isinstance(click, RuleImage) or isinstance(click, RuleOcr):
            self.device.click(x=x, y=y, control_name=click.name)

        # 执行后，如果有限制时间，则重置限制时间
        if interval:
            self.interval_timer[click.name].reset()
            return True
        return False

    def ocr_appear(self, target: RuleOcr, interval: float = None) -> bool:
        """
        ocr识别目标
        :param interval:
        :param target:
        :return: 如果target有keyword或者是keyword存在，返回是True，否则返回False
                 但是没有指定keyword，返回的是匹配到的值，具体取决于target的mode
        """
        if not isinstance(target, RuleOcr):
            return None

        if interval:
            if target.name in self.interval_timer:
                # 如果传入的限制时间不一样，则替换限制新的传入的时间
                if self.interval_timer[target.name].limit != interval:
                    self.interval_timer[target.name] = Timer(interval)
            else:
                # 如果没有限制时间，则创建限制时间
                self.interval_timer[target.name] = Timer(interval)
            # 如果时间还没到达，则不执行
            if not self.interval_timer[target.name].reached():
                return None

        result = target.ocr(self.device.image)
        appear = False

        if not target.keyword or target.keyword == '':
            appear = False
        match target.mode:
            case OcrMode.FULL:  # 全匹配
                appear = result != (0, 0, 0, 0)
            case OcrMode.SINGLE:
                appear = result == target.keyword
            case OcrMode.DIGIT:
                appear = result == int(target.keyword)
            case OcrMode.DIGITCOUNTER:
                appear = result == target.ocr_str_digit_counter(target.keyword)
            case OcrMode.DURATION:
                appear = result == target.parse_time(target.keyword)

        if interval and appear:
            self.interval_timer[target.name].reset()

        return appear

    def ocr_appear_click(self,
                         target: RuleOcr,
                         action: Union[RuleClick, RuleLongClick] = None,
                         interval: float = None,
                         duration: float = None) -> bool:
        """
        ocr识别目标，如果目标存在，则触发动作
        :param target:
        :param action:
        :param interval:
        :param duration:
        :return:
        """
        appear = self.ocr_appear(target, interval)

        if not appear:
            return False

        if action:
            x, y = action.coord()
            self.click(action, interval)
        else:
            x, y = target.coord()
            self.device.click(x=x, y=y, control_name=target.name)
        return True

    def list_find(self, target: RuleList, name: str | list[str]) -> bool:
        """
        会一致在列表寻找目标，找到了就退出。
        如果是图片列表会一直往下找
        如果是纯文字的，会自动识别自己的位置，根据位置选择向前还是向后翻
        :param target:
        :param name:
        :return:
        """
        if target.is_image:
            while True:
                self.screenshot()
                result = target.image_appear(self.device.image, name=name)
                if result is not None:
                    return result
                x1, y1, x2, y2 = target.swipe_pos()
                self.device.swipe(p1=(x1, y1), p2=(x2, y2))

        elif target.is_ocr:
            while True:
                self.screenshot()
                result = target.ocr_appear(self.device.image, name=name)
                if isinstance(result, tuple):
                    return result

                after = True
                if isinstance(result, int) and result > 0:
                    after = True
                elif isinstance(result, int) and result < 0:
                    after = False

                x1, y1, x2, y2 = target.swipe_pos(number=1, after=after)
                self.device.swipe(p1=(x1, y1), p2=(x2, y2))
                sleep(1)  # 等待滑动完成， 还没想好如何优化

    def set_next_run(self, task: str, finish: bool = False,
                     success: bool = None, server: bool = True, target: datetime = None) -> None:
        """
        设置下次运行时间  当然这个也是可以重写的
        :param target: 可以自定义的下次运行时间
        :param server: True
        :param success: 判断是成功的还是失败的时间间隔
        :param task: 任务名称，大驼峰的
        :param finish: 是完成任务后的时间为基准还是开始任务的时间为基准
        :return:
        """
        if finish:
            start_time = datetime.now().replace(microsecond=0)
        else:
            start_time = self.start_time
        self.config.task_delay(task, start_time=start_time, success=success, server=server, target=target)

    #  ---------------------------------------------------------------------------------------------------------------
    #
    #  ---------------------------------------------------------------------------------------------------------------
    def ui_reward_appear_click(self, screenshot=False) -> bool:
        """
        如果出现 ‘获得奖励’ 就点击
        :return:
        """
        if screenshot:
            self.screenshot()
        return self.appear_then_click(self.I_UI_REWARD, action=self.C_UI_REWARD, interval=0.4, threshold=0.6)

    def ui_get_reward(self, click_image: RuleImage or RuleOcr or RuleClick, click_interval: float=1):
        """
        传进来一个点击图片 或是 一个ocr， 会点击这个图片，然后等待‘获得奖励’，
        最后当获得奖励消失后 退出
        :param click_interval:
        :param click_image:
        :return:
        """
        while 1:
            self.screenshot()

            if self.ui_reward_appear_click():
                sleep(0.5)
                while 1:
                    self.screenshot()
                    # 等待动画结束
                    if not self.appear(self.I_UI_REWARD, threshold=0.6):
                        logger.info('Get reward success')
                        break

                    # 一直点击
                    if self.ui_reward_appear_click():
                        continue
                break

            if isinstance(click_image, RuleImage):
                if self.appear_then_click(click_image, interval=click_interval):
                    continue
            elif isinstance(click_image, RuleOcr):
                if self.ocr_appear_click(click_image, interval=click_interval):
                    continue
            elif isinstance(click_image, RuleClick):
                if self.click(click_image, interval=click_interval):
                    continue

        return True

    def ui_click(self, click, stop, interval=1):
        """
        循环的一个操作，直到出现stop
        :param click:
        :param stop:
        :parm interval
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear(stop):
                break
            if isinstance(click, RuleImage) and self.appear_then_click(click, interval=interval):
                continue
            if isinstance(click, RuleClick) and self.click(click, interval=interval):
                continue
            elif isinstance(click, RuleOcr) and self.ocr_appear_click(click, interval=interval):
                continue

    def ui_click_until_disappear(self, click, interval: float =1):
        """
        点击一个按钮直到消失
        :param interval:
        :param click:
        :return:
        """
        while 1:
            self.screenshot()
            if not self.appear(click):
                break
            elif self.appear_then_click(click, interval=interval):
                continue
