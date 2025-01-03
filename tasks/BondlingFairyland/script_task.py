# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from tasks.Component.GeneralRoom.general_room import GeneralRoom

import numpy as np
from time import sleep
from cached_property import cached_property
from datetime import datetime, timedelta
from tasks.BondlingFairyland.general_invite import GeneralInvite
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets

from tasks.base_task import BaseTask
from tasks.GameUi.game_ui import GameUi
from tasks.BondlingFairyland.config import (BondlingFairyland, BondlingMode,
                                            BondlingClass,
                                            BondlingSwitchSoul, BondlingConfig, UserStatus)
from tasks.BondlingFairyland.assets import BondlingFairylandAssets
from tasks.BondlingFairyland.battle import BondlingBattle
from tasks.BondlingFairyland.config_battle import BattleConfig
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul, switch_parser
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.GameUi.page import page_main, page_bondling_fairyland, page_shikigami_records

from module.atom.image import RuleImage
from module.logger import logger
from module.exception import TaskEnd
from tasks.Component.GeneralRoom.assets import GeneralRoomAssets
from module.base.timer import Timer
from datetime import timedelta, time


class BondlingNumberMax(Exception):
    pass


class ScriptTask(GameUi, GeneralInvite, GeneralRoom, BondlingBattle, SwitchSoul, BondlingFairylandAssets):
    ball_pos_list = [None, None, None, None, None]  # 用于记录每一个位置的球是否出现
    first_catch = True  # 用于记录是否是第一次捕捉

    def run(self):
        # 引用配置
        cong = self.config.bondling_fairyland

        # 御魂切换方式一
        if cong.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(cong.switch_soul_config.switch_group_team)
        # 御魂切换方式二
        if cong.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(cong.switch_soul_config.group_name, cong.switch_soul_config.team_name)

        self.ui_get_current_page()
        self.ui_goto(page_bondling_fairyland)

        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_BONDLING_FAIRYLAND, interval=1):
                break
            if self.appear(self.I_BALL_HELP, interval=1):
                self.ui_get_current_page()
                self.ui_goto(page_bondling_fairyland)
                continue

        limit_count = cong.bondling_config.limit_count
        self.current_count = 0
        self.limit_count: int = limit_count

        if UserStatus.handoff1 == cong.bondling_config.user_status:
            self.limit_count: int = limit_count//2
            self.switch_ball()
        if UserStatus.handoff2 == cong.bondling_config.user_status:
            self.limit_count: int = limit_count//2
            self.run_member()
            self.current_count = 0
            self.ui_get_current_page()
            self.ui_goto(page_bondling_fairyland)
            self.switch_ball()

        match cong.bondling_config.user_status:
            case UserStatus.LEADER:
                self.switch_ball()
            case UserStatus.MEMBER:
                self.run_member()
            case UserStatus.ALONE:
                self.switch_ball()
            case _:
                logger.error('Unknown user status')

    def run_member(self):
        logger.info('Start run member')
        self.ui_get_current_page()
        # 开始等待队长拉人
        wait_time = self.config.bondling_fairyland.invite_config.wait_time
        wait_timer = Timer(wait_time.minute * 60)
        wait_timer.start()
        success = True

        # 进入战斗流程
        self.device.stuck_record_add('BATTLE_STATUS_S')

        while 1:

            self.screenshot()

            # 等待超时
            logger.info("开始等待队长拉人:" + str(wait_timer.current()))
            if wait_timer.reached():
                logger.warning('wait_timer timeout')
                break

            # if self.current_count >= self.limit_count:
            #     logger.info('Orochi count limit out')
            #     break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('BondlingFairyland time limit out')
                break

            if self.check_then_accept():
                continue

            if self.is_in_room():
                logger.info("契灵：进入组队房间！")
                if self.wait_battle(wait_time=self.config.bondling_fairyland.invite_config.wait_time):
                    self.run_battle(self.config.bondling_fairyland.battle_config, limit_count=self.limit_count)
                    wait_timer.reset()
                    # 进入战斗流程
                    self.device.stuck_record_add('BATTLE_STATUS_S')
                else:
                    break
            # 队长秒开的时候，检测是否进入到战斗中
            elif self.check_take_over_battle(False, config=self.config.bondling_fairyland.battle_config):
                wait_timer.reset()
                # 进入战斗流程
                self.device.stuck_record_add('BATTLE_STATUS_S')
                continue

        while 1:
            # 有一种情况是本来要退出的，但是队长邀请了进入的战斗的加载界面
            if self.appear(self.I_GI_HOME) or self.appear(self.I_GI_EXPLORE) or self.appear(self.I_CHECK_BONDLING_FAIRYLAND):
                break
            # 如果可能在房间就退出
            if self.exit_room():
                pass
            # 如果还在战斗中，就退出战斗
            if self.exit_battle():
                pass
                # 引用配置
        if UserStatus.MEMBER == self.config.bondling_fairyland.bondling_config.user_status:
            self.ui_get_current_page()
            self.ui_goto(page_main)
            self.set_next_run(task='BondlingFairyland', finish=True, success=True)
            raise TaskEnd


    def switch_ball(self):
        cong = self.config.bondling_fairyland

        bondling_config = cong.bondling_config
        bondling_switch_soul = cong.bondling_switch_soul
        battle_config = cong.battle_config

        current_ball = 0  # 用于记录当前捕捉的球的位置
        success = True
        while 1:

            if not self.in_search_ui(screenshot=True):
                sleep(0.4)
                continue

            if current_ball == 0:
                if self.run_stone(bondling_config.bondling_stone_enable, bondling_config.bondling_stone_class):
                    current_ball = 5
                    logger.info(f'Current ball number: {current_ball} ')

                if current_ball == 5:
                    continue
                if self.run_search(bondling_config):
                    current_ball = 5
                    logger.info(f'Current ball number: {current_ball} ')
                else:
                    break

            if bondling_config.bondling_mode != BondlingMode.MODE1:
                if self.ball_click(current_ball):
                    pass
                else:
                    # 如果点击了四次还是没有进去，那可能说明这个位置没有球
                    current_ball -= 1
                    logger.info(f'Current ball number: {current_ball} ')
                    continue

                try:
                    # 执行捕捉
                    if self.run_catch(bondling_config, bondling_switch_soul, battle_config):
                        current_ball -= 1
                        logger.info(f'Catch successful and current ball number: {current_ball} ')
                    else:
                        break
                except BondlingNumberMax:
                    logger.error('Bondling number max, exit')
                    self.config.notifier.push(title='契灵之境', content='契灵数量已达上限500，请及时处理')
                    success = False
                    break
            else:
                # 否则就是模式1
                break

        # 退出的时候如果是在结契的界面，要退回到探查界面
        while 1:
            self.screenshot()
            if self.in_search_ui():
                break
            if self.in_catch_ui():
                self.appear_then_click(self.I_BACK_Y, interval=1)
        logger.info('BondlingFairyland task finished')

        self.ui_get_current_page()
        self.ui_goto(page_main)
        self.set_next_run(task='BondlingFairyland', finish=True, success=True)
        raise TaskEnd


    def run_stone(self, bondling_stone_enable: bool, bondling_stone_class: BondlingClass):
        """
        使用结契石 进行召唤 契灵
        :param bondling_stone_class:
        :return:
        (0) 不开启使用结契石，(探查界面)返回False
        (1) 五个球满了，(探查界面)返回True
        (2) 没有结契石了，(探查界面)返回False
        """
        if not bondling_stone_enable:
            return False

        while 1:
            self.screenshot()
            # 检查是不是在探查界面，
            if not self.in_search_ui(screenshot=False):
                continue
            # 如果没有石头了
            cu, res, total = self.O_B_STONE_NUMBER.ocr(self.device.image)
            if cu == 0 and cu + res == total:
                logger.warning(f'No bondling stone')
                return False
            # 如果五个球满了
            click_count = 0
            while 1:
                self.screenshot()
                if click_count >= 2:
                    logger.info(f'Ball is full')
                    return True
                if not self.appear(self.I_STONE_ENTER):
                    # 这时进入到了召唤的界面
                    self.wait_until_appear(self.I_STONE_SURE)
                    action_click = None
                    match bondling_stone_class:
                        case BondlingClass.LITTLE_KURO: action_click = self.C_LEFT_1
                        case BondlingClass.SNOWBALL: action_click = self.C_LEFT_2
                        case BondlingClass.AZURE_BASAN: action_click = self.C_LEFT_3
                        case BondlingClass.TOMB_GUARD: action_click = self.C_LEFT_4
                    sleep(0.5)
                    self.click(action_click)

                    # 点击召唤
                    while 1:
                        self.screenshot()
                        if not self.appear(self.I_STONE_SURE):
                            break
                        if self.appear_then_click(self.I_STONE_SURE, interval=1):
                            continue
                    break

                if self.appear_then_click(self.I_STONE_ENTER, interval=1):
                    click_count += 1
                    continue

    def run_search(self, bondling_config: BondlingConfig):
        """
        运行探查
        :return:
        (1) 超出战斗的次数的了，(探查页面)返回False
        (2) 超过时间限制了，(探查页面)返回False
        (3) 打满五只球了，(探查界面)返回True
        """
        self.lock_team()
        while 1:
            # 检查是不是在探查界面，
            if not self.in_search_ui(screenshot=True):
                continue
            # 检查是否有挑战次数
            if self.current_count >= bondling_config.limit_count:
                logger.warning(f'No challenge count, exit')
                return False
            # 检查是否到了限制时间
            if datetime.now() - self.start_time >= self.limit_time:
                logger.warning(f'No time, exit')
                return False

            if self.click_search():
                self.run_general_battle(self.general_battle_config)
            else:
                logger.warning(f'Full five ball')
                return True

    def run_catch(self, bondling_config: BondlingConfig,
                        bondling_switch_soul: BondlingSwitchSoul,
                        battle_config: BattleConfig):
        """
        执行捕捉的(确保进入了结契界面)
        :return:
        (1) 盘子没了，返回False (退出页面是结契界面)
        (2) 时间到了，返回False (退出页面是结契界面)
        (3) 挑战次数到了，返回False (退出页面是结契界面)
        (4) 捕获成功，返回True (退出页面是捕获的页面)
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
                logger.info(f'{bondling_class.name} switch soul is not set, skip')
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

        # 开始执行循环
        success =True
        while 1:
            self.screenshot()

            # 如果不在结契界面，就等待
            if not self.in_catch_ui():
                continue

            # 检查是否有盘子
            if not check_plate_number(target_plate):
                logger.warning(f'No plate number, exit')
                return False
            # 检查是否有挑战次数
            if self.current_count >= bondling_config.limit_count:
                logger.warning(f'No challenge count, exit')
                return False
            # 检查是否到了限制时间
            if datetime.now() - self.start_time >= self.limit_time:
                logger.warning(f'No time, exit')
                return False

            # 引用配置
            cong = self.config.bondling_fairyland
            match cong.bondling_config.user_status:
                case UserStatus.LEADER:
                    if self.run_leader():
                        return success
                case UserStatus.handoff1:
                    if self.run_leader():
                        return success
                case UserStatus.handoff2:
                    if self.run_leader():
                        return success
                case UserStatus.ALONE:
                    self.run_alone()
                    if self.run_battle(battle_config, limit_count=self.limit_count):
                        return success
                case _:
                    logger.error('Unknown user status')


    def is_room_dead(self) -> bool:
        # 如果在探索界面或者是出现在组队界面，那就是可能房间死了
        sleep(0.5)
        if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
            sleep(0.5)
            if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
                return True
        return False

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
        logger.info(f'Click ball {index}')
        while 1:
            self.screenshot()
            if self.appear(self.I_CLICK_CAPTION):
                return True
            if click_count >= 5:
                return False
            # 点击
            if self.click(click_target, interval=1):
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

    @cached_property
    def limit_time(self) -> timedelta:
        if not self.config.bondling_fairyland.bondling_config.limit_time:
            return timedelta(minutes=20)
        limit_time = self.config.bondling_fairyland.bondling_config.limit_time
        return timedelta(hours=limit_time.hour, minutes=limit_time.minute, seconds=limit_time.second)

    def run_alone(self):
        """
        单人 挑战， 主要是结契时的挑战
        """
        click_count = 0
        while 1:
            self.screenshot()
            if not self.appear(self.I_CLICK_CAPTION, threshold=0.7):
                break
            if self.appear_then_click(self.I_BALL_FIRE, interval=1):
                click_count += 1
                continue
            if click_count >= 6:
                logger.error('Click fire failed')
                logger.error('You might need to check your bondling number. It most possibly arrived to the max 500')
                raise BondlingNumberMax
            # 某些活动的时候出现 “选择共鸣的阴阳师”
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue

    def run_leader(self):

        """
        点击 求援， 组队模式
        """
        click_count = 0
        # target = None
        # appear1 = self.I_CREATE_ENSURE.match(self.device.image)
        while 1:
            self.screenshot()
            if click_count >= 6:
                logger.error('Click fire failed')
                logger.error('You might need to check your bondling number. It most possibly arrived to the max 500')
                raise BondlingNumberMax
            if self.appear(self.I_CREATE_TEAM):
                break
            # 某些活动的时候出现 “选择共鸣的阴阳师”
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            # 盘子满了继续
            if self.check_and_invite(True):
                continue
            # 求援
            if self.appear_then_click(self.I_BALL_HELP, interval=1):
                click_count += 1
                continue

        while 1:
            self.screenshot()
            if self.ensure_private():
                break
        while 1:
            self.screenshot()

            if self.appear(self.I_GI_IN_ROOM):
                break
            if self.appear_then_click(self.I_CREATE_TEAM, interval=1):
                continue

        # 邀请队友
        success = True
        is_first = True
        # 这个时候我已经进入房间了哦
        while 1:
            self.screenshot()

            # 无论胜利与否, 都会出现是否邀请一次队友
            # 区别在于，失败的话不会出现那个勾选默认邀请的框
            self.check_and_invite(True)

            if self.current_count >= self.limit_count:
                if self.appear(self.I_GI_IN_ROOM):
                    # 次数达到也要邀请好友进房间,然后退出,不然队员无法判断是否完成契灵,出现异常
                    self.run_invite(config=self.config.bondling_fairyland.invite_config, is_over=False)
                    # 等待三秒让队员进房间,避免队员没进房间出现异常
                    sleep(3)
                    logger.info('bondling_fairyland count limit out')
                    break

            if datetime.now() - self.start_time >= self.limit_time:
                if self.appear(self.I_GI_IN_ROOM):
                    logger.info('bondling_fairyland time limit out')
                    break

            if self.appear(self.I_GI_IN_ROOM):
                # 点击挑战
                if not is_first:
                    if self.run_invite(config=self.config.bondling_fairyland.invite_config):
                        self.run_battle(self.config.bondling_fairyland.battle_config, limit_count=self.limit_count)
                    else:
                        # 邀请失败，退出任务
                        logger.warning('Invite failed and exit this bondling_fairyland task')
                        success = False
                        break

                # 第一次会邀请队友
                if is_first:
                    if not self.run_invite(config=self.config.bondling_fairyland.invite_config, is_first=True):
                        logger.warning('Invite failed and exit this bondling_fairyland task')
                        success = False
                        break
                    else:
                        is_first = False
                        self.run_battle(self.config.bondling_fairyland.battle_config, limit_count=self.limit_count)
                        continue
            if self.appear(self.I_CHECK_BONDLING_FAIRYLAND):
                return True
        # 当结束或者是失败退出循环的时候只有两个UI的可能，在房间或者是在组队界面
        # 如果在房间就退出
        if self.exit_room():
            pass
        # 如果在组队界面就退出
        if self.exit_team():
            pass

        self.ui_get_current_page()
        self.ui_goto(page_bondling_fairyland)
        # 引用配置
        if UserStatus.handoff1 == self.config.bondling_fairyland.bondling_config.user_status:
            self.current_count = 0
            self.run_member()
        self.ui_get_current_page()
        self.ui_goto(page_main)
        self.set_next_run(task='BondlingFairyland', finish=True, success=True)
        raise TaskEnd

    def wait_battle(self, wait_time: time) -> bool:
        """
        在房间等待,(要求保证在房间里面) 队长开启战斗
        如果队长跑路了，或者的等待了很久还没开始
        :return: 如果成功进入战斗（反正就是不在房间 ）返回 True
                 如果失败了，（退出房间）返回 False
        """
        self.timer_emoji = Timer(15)
        self.timer_emoji.start()
        wait_second = wait_time.second + wait_time.minute * 60
        self.timer_wait = Timer(wait_second)
        self.timer_wait.start()
        logger.info(f'Wait battle {wait_second} seconds')
        success = True
        while 1:
            self.screenshot()

            # 如果自己在探索界面或者是庭院，那就是房间已经被销毁了
            if self.appear(self.I_GI_HOME) or self.appear(self.I_GI_EXPLORE) or self.appear(self.I_CHECK_BONDLING_FAIRYLAND):
                logger.warning('Room destroyed')
                success = False
                break

            if self.timer_wait.reached():
                logger.warning('Wait battle time out')
                success = False
                break

            if self.appear(self.I_EXIT):
                success = True
                logger.info("契灵：进入战斗页面！")
                break

            # # 判断是否进入战斗
            # if self.is_in_room(is_screenshot=False):
            #     logger.info("契灵：进入组队房间！")
            #     if self.timer_emoji.reached():
            #         self.timer_emoji.reset()
            #         self.appear_then_click(self.I_GI_EMOJI_1)
            #         self.appear_then_click(self.I_GI_EMOJI_2)
            # else:
            #     if self.appear(self.I_EXIT):
            #         logger.info("契灵：进入战斗页面！")
            #         break
            #     if self.appear(self.I_CHECK_BONDLING_FAIRYLAND):
            #         logger.info("契灵：探查页面！")
            #         success = False
            #         break

        # 调出循环只有这些可能性：
        # 1. 进入战斗（ui是战斗）
        # 2. 队长跑路（自己还是在房间里面）
        # 3. 等待时间到没有开始（还是在房间里面）
        # 4. 房间的时间到了被迫提出房间（这个时候来到了探索界面）
        if not success:
            logger.info('Leave room')
            self.exit_room()

        return success

    def exit_team(self) -> bool:
        """
        在组队界面 退出组队的界面， 返回到庭院或者是你一开始进入的入口
        :return:
        """
        if self.appear(self.I_CHECK_TEAM):
            logger.info('Exit team ui')
            while 1:
                self.screenshot()
                if not self.appear(self.I_CHECK_TEAM):
                    return True
                if self.appear_then_click(self.I_GR_BACK_YELLOW, interval=0.5):
                    continue

    def in_catch_ui(self, screenshot=False) -> bool:
        """
        判断是否在结契的总界面
        :return:
        """
        if screenshot:
            self.screenshot()
        return self.appear(self.I_BALL_FIRE)

    def in_search_ui(self, screenshot=False) -> bool:
        """
        判断是否在探查的总界面
        :return:
        """
        if screenshot:
            self.screenshot()
        return self.appear(self.I_BF_STORE)

    def click_search(self) -> bool:
        """
        点击探查
        :return: 如果五个球满了 就返回False。如果进入战斗不出现点击按钮那就是返回True
        """
        count = 0
        while 1:
            self.screenshot()
            if count >= 3:
                return False
            if not self.appear(self.I_BF_SEARSH):
                return True
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                continue
            if self.appear_then_click(self.I_BF_SEARSH, interval=2):
                count += 1
                continue
        return False

    def check_then_accept(self) -> bool:
        """
        队员接受邀请
        :return:
        """
        if not self.appear(self.I_I_ACCEPT):
            return False
        logger.info('Click accept')

        accept_timer = Timer(5)
        accept_timer.start()
        logger.info("识别到队长邀请，准备点击接受")
        while 1:
            self.screenshot()

            # 等待超时
            logger.info(str(accept_timer.current()))
            if accept_timer.reached():
                logger.warning('accept_timer timeout')
                break

            if self.is_in_room():
                logger.info("进入到组队房间！is_in_room")
                return True
            # 被秒开
            # https://github.com/runhey/OnmyojiAutoScript/issues/230
            if self.appear(GeneralBattleAssets.I_EXIT):
                logger.info("进入到组队房间！")
                return False
            if self.appear_then_click(self.I_I_NO_DEFAULT, interval=1):
                continue
            if self.appear_then_click(self.I_GI_SURE, interval=1):
                continue
            if self.appear_then_click(self.I_I_ACCEPT_DEFAULT, interval=1):
                continue
            if self.appear_then_click(self.I_I_ACCEPT, interval=1):
                continue
        return True

    @cached_property
    def general_battle_config(self):
        gbc = GeneralBattleConfig()
        gbc.lock_team_enable = True
        gbc.preset_enable = False
        gbc.green_enable = False
        gbc.random_click_swipt_enable = False
        return gbc


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    import cv2

    config = Config('oas1')
    device = Device(config)
    task = ScriptTask(config, device)
    image = task.screenshot()

    con = config.bondling_fairyland
    # task.lock_team()
    task.run()
