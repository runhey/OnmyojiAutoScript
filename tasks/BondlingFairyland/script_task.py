# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import numpy as np
from cached_property import cached_property

from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.BondlingFairyland.config import (BondlingFairyland, BondlingMode,
                                            BondlingClass,
                                            BondlingSwitchSoul, BondlingConfig)
from tasks.BondlingFairyland.assets import BondlingFairylandAssets
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul, switch_parser

from module.atom.image import RuleImage
from module.logger import logger

class ScriptTask(GameUi, GeneralBattle, SwitchSoul, BondlingFairylandAssets):

    ball_pos_list = [None, None, None, None, None]  # 用于记录每一个位置的球是否出现
    first_catch = True  # 用于记录是否是第一次捕捉

    def run(self):
        pass

    def run_search(self):
        """
        运行探查
        :return:
        """
    def run_catch(self, bondling_config: BondlingConfig, bondling_switch_soul: BondlingSwitchSoul):
        """
        执行捕捉的(确保进入了结契界面)
        :return:
        (1) 盘子没了，返回False (退出页面是结契界面)
        (2) 时间到了，返回False (退出页面是结契界面)
        (3) 挑战次数到了，返回False (退出页面是结契界面)
        (4) 捕获成功，返回True (退出页面是结契界面)
        """
        self.lock_team()
        if self.first_catch:
            self.first_catch = False
            self.capture_setting(bondling_config.bondling_mode)

        target_plate = None
        match bondling_config.bondling_mode:
            case BondlingMode.MODE2: target_plate = self.O_B_LOW_NUMBER
            case BondlingMode.MODE3: target_plate = self.O_B_MEDIUM_NUMBER
        def check_plate_number(target_plate):
            self.screenshot()
            cu, res, total = target_plate.ocr(self.device.image)
            if cu == 0 and cu + res == total:
                logger.warning(f'No plate number, exit')
                return False
            return True
        if not check_plate_number(target_plate):
            return False

        def switch_soul(bondling_class: BondlingClass):
            # 按照结契的来切换御魂
            group_team: str = None
            match bondling_class:
                case BondlingClass.AZURE_BASAN: group_team = bondling_switch_soul.azure_basan_switch
                case BondlingClass.SNOWBALL: group_team = bondling_switch_soul.snowball_switch
                case BondlingClass.LITTLE_KURO: group_team = bondling_switch_soul.little_kuro_switch
                case BondlingClass.TOMB_GUARD: group_team = bondling_switch_soul.tomb_guard_switch
            group_team = switch_parser(group_team)
            if group_team == [-1, -1]:
                logger.info(f'{bondling_class.name } switch soul is not set, skip')
                return False
            self.enter_shikigami_records()
            self.run_switch_soul(tuple(group_team))
            # 返回的时候可能会多点一次导致 返回到探查界面
            self.exit_shikigami_records()

        bondling_class = self.get_bondling_class()
        first_switch_soul = True
        if bondling_switch_soul.auto_switch_soul:
            first_switch_soul = False
            switch_soul(bondling_class)



    @cached_property
    def balls_target(self) -> list[RuleImage]:
        """
        获取所有的球的图片
        :return:
        """
        result = [self.I_BF_LOCAL_1_AZURE_BASAN,
                  self.I_BF_LOCAL_2_SNOWBALL,
                  self.I_BF_LOCAL_3_LITTLE_KURO,
                  self.I_BF_LOCAL_5_TOMB_GUARD]
        return result

    @cached_property
    def balls_roi(self) -> list[tuple]:
        """
        获取球的五个位置是识别区域
        :return:
        """
        result = [self.I_BF_LOCAL_1_AZURE_BASAN.roi_back,
                  self.I_BF_LOCAL_2_SNOWBALL.roi_back,
                  self.I_BF_LOCAL_3_LITTLE_KURO.roi_back,
                  self.I_BF_LOCAL_4_NONE.roi_back,
                  self.I_BF_LOCAL_5_TOMB_GUARD.roi_back]
        return result

    def roi_appear_ball(self, roi: tuple, image: np.ndarray) -> tuple | None:
        """
        判断某个固定的区域是否出现了球
        :param roi:
        :param image:
        :return: 如果出现了，那就返回可以点击的区域，如果没有出现，那就返回None
        """
        for ball in self.balls_target:
            ball.roi_back = list(roi)
            if ball.match(image, threshold=0.8):
                logger.info(f'Find ball {ball.name}')
                logger.info(f'Ball roi {ball.roi_front}')
                return ball.roi_front
        return None

    def ball_number(self) -> int:
        """
        !!! 弃用，原因是发现进行探查的时候会出现： 你的阴阳师会挡住球的位置，导致识别不到球

        获取当前球的数量, 探查阶段优化使用的，但是在你抓完契灵后记得清空
        :return:
        """
        self.screenshot()
        count = 0
        for index, ball_pos in enumerate(self.ball_pos_list):
            if ball_pos is not None:
                count += 1
                continue
            appear_roi = self.roi_appear_ball(self.balls_roi[index], self.device.image)
            if appear_roi is not None:
                count += 1
                self.ball_pos_list[index] = appear_roi

        return count

    def use_stone(self, bondling_class: BondlingClass) -> bool:
        """
        使用契灵石
        :param bondling_class:
        :return: 如果使用成功，那就返回True 如果已经有五个了返回False
        """

        return False

    def click_search(self) -> bool:
        """
        点击探查
        :return: 如果进入战斗返回True，如果五个球满了返回False
        """
        return False

    def ball_click(self, index: int) -> bool:
        """
        点击球, 进去结契战斗的界面
        :param index:
        :return:
        """
        def get_click_target(ind: int):
            if ind > 5 or ind < 1:
                raise ValueError('index must be 1-5')
            match = {
                1: self.C_STONE_1,
                2: self.C_STONE_2,
                3: self.C_STONE_3,
                4: self.C_STONE_4,
                5: self.C_STONE_5,
            }
            return match[ind]

        click_target = get_click_target(index)
        click_count = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_CLICK_CAPTION):
                return True
            if click_count >= 4:
                return False
            # 点击
            self.click(click_target, interval=1)
            click_count += 1

    def capture_setting(self, mode: BondlingMode) -> None:
        """
        第一次进入任务的时候触发这一项方法：为了确保用户的选择默认是正确的
        在结契的跳转页面，进入结契设置，按照模式来勾选
        :param mode:
        :return:
        """
        if mode == BondlingMode.MODE1:
            return None
        logger.info(f'Capture setting mode: {mode}')
        while 1:
            self.screenshot()
            if self.appear(self.I_CAPTION_ENSURE):
                break
            if self.appear_then_click(self.I_CLICK_CAPTION, interval=1):
                continue

        while 1:
            self.screenshot()
            if self.appear(self.I_C_AUTO_TRUE):
                break
            if self.appear_then_click(self.I_C_AUTO_FALSE, interval=1):
                continue

        target_true = None
        target_false = None
        target_first = None
        if mode == BondlingMode.MODE3:
            target_true = self.I_C_MIDUM_TRUE
            target_false = self.I_C_MIDUM_FALSE
            target_first = self.I_C_FIRST_ENABLE
        elif mode == BondlingMode.MODE2:
            target_true = self.I_C_LOW_TRUE
            target_false = self.I_C_LOW_FALSE
            target_first = self.I_C_FIRST_DISABLE
        while 1:
            self.screenshot()
            if self.appear(target_true):
                break
            if self.appear_then_click(target_false, interval=1):
                continue
        while 1:
            self.screenshot()
            if not self.appear(target_first):
                break
            if self.appear_then_click(target_first, interval=1):
                continue

        # 点击确定退出
        while 1:
            self.screenshot()
            if not self.appear(self.I_CAPTION_ENSURE):
                break
            if self.appear_then_click(self.I_CAPTION_ENSURE, interval=1):
                continue

    def enter_shikigami_records(self) -> None:
        """
        进入式神录(在探查或者是结契的界面)
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_RECORDS):
                break
            if self.appear_then_click(self.I_BF_RECORDS, interval=1):
                continue
            if self.appear_then_click(self.I_BALL_RECORDS, interval=1):
                continue

    def lock_team(self):
        """
        锁定队伍(在探查或者是结契的界面)
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear(self.I_BALL_LOCK):
                break
            if self.appear(self.I_BF_LOCK):
                break
            if self.appear_then_click(self.I_BALL_UNLOCK, interval=1):
                continue
            if self.appear_then_click(self.I_BF_UNLOCK, interval=1):
                continue

    def get_bondling_class(self) -> BondlingClass or None:
        """
        获取契灵的种类 (这个不应该一开始就调用因为这些会有出场动画)
        :return:
        """
        self.screenshot()
        if self.appear(self.I_TOMB_GUARD):
            return BondlingClass.TOMB_GUARD
        elif self.appear(self.I_SNOWBALL):
            return BondlingClass.SNOWBALL
        elif self.appear(self.I_LITTLE_KURO):
            return BondlingClass.LITTLE_KURO
        elif self.appear(self.I_AZURE_BASAN, threshold=0.7):
            return BondlingClass.AZURE_BASAN
        return None



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    import cv2

    config = Config('oas1')
    device = Device(config)
    task = ScriptTask(config, device)
    image = task.screenshot()
    # print(task.roi_appear_ball(task.I_BF_LOCAL_3_LITTLE_KURO.roi_back, image))
    # print(task.ball_number())
    con = config.bondling_fairyland
    task.run_catch(con.bondling_config, con.bondling_switch_soul)

