# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import random
from time import sleep
from datetime import time, datetime, timedelta

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.GeneralBuff.general_buff import GeneralBuff
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_soul_zones, page_shikigami_records
from tasks.FallenSun.assets import FallenSunAssets
from tasks.FallenSun.config import FallenSun, UserStatus
from module.logger import logger
from module.exception import TaskEnd

class ScriptTask(GeneralBattle, GeneralInvite, GeneralBuff, GeneralRoom, GameUi, SwitchSoul, FallenSunAssets):

    def run(self) -> bool:
        # 御魂切换方式一
        if self.config.fallen_sun.switch_soul.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(self.config.fallen_sun.switch_soul.switch_group_team)

        # 御魂切换方式二
        if self.config.fallen_sun.switch_soul.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(self.config.fallen_sun.switch_soul.group_name,
                                         self.config.fallen_sun.switch_soul.team_name)

        limit_count = self.config.fallen_sun.fallen_sun_config.limit_count
        limit_time = self.config.fallen_sun.fallen_sun_config.limit_time
        self.current_count = 0
        self.limit_count: int = limit_count
        self.limit_time: timedelta = timedelta(hours=limit_time.hour, minutes=limit_time.minute, seconds=limit_time.second)

        self.ui_get_current_page()
        self.ui_goto(page_main)
        config: FallenSun = self.config.fallen_sun

        success = True
        match config.fallen_sun_config.user_status:
            case UserStatus.LEADER: success = self.run_leader()
            case UserStatus.MEMBER: success = self.run_member()
            case UserStatus.ALONE: self.run_alone()
            case UserStatus.WILD: self.run_wild()
            case _: logger.error('Unknown user status')

        # 下一次运行时间
        if success:
            self.set_next_run('FallenSun', finish=True, success=True)
        else:
            self.set_next_run('FallenSun', finish=False, success=False)

        raise TaskEnd

    def fallen_sun_enter(self) -> bool:
        logger.info('Enter fallen_sun')
        while True:
            self.screenshot()
            if self.appear(self.I_FORM_TEAM):
                return True
            if self.appear_then_click(self.I_FALLEN_SUN, interval=1):
                continue

    def check_layer(self, layer: str) -> bool:
        """
        检查挑战的层数, 并选中挑战的层
        :return:
        """
        pos = self.list_find(self.L_LAYER_LIST, layer)
        if pos:
            self.device.click(x=pos[0], y=pos[1])
            return True

    def check_lock(self, lock: bool = True) -> bool:
        """
        检查是否锁定阵容, 要求在八岐大蛇界面
        :param lock:
        :return:
        """
        logger.info('Check lock: %s', lock)
        if lock:
            while 1:
                self.screenshot()
                if self.appear(self.I_FALLEN_SUN_LOCK):
                    return True
                if self.appear_then_click(self.I_FALLEN_SUN_UNLOCK, interval=1):
                    continue
        else:
            while 1:
                self.screenshot()
                if self.appear(self.I_FALLEN_SUN_UNLOCK):
                    return True
                if self.appear_then_click(self.I_FALLEN_SUN_LOCK, interval=1):
                    continue

    def run_leader(self):
        logger.info('Start run leader')
        self.ui_get_current_page()
        self.ui_goto(page_soul_zones)
        self.fallen_sun_enter()
        layer = self.config.fallen_sun.fallen_sun_config.layer
        self.check_layer(layer)
        self.check_lock(self.config.fallen_sun.general_battle_config.lock_team_enable)
        # 创建队伍
        logger.info('Create team')
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_TEAM):
                break
            if self.appear_then_click(self.I_FORM_TEAM, interval=1):
                continue
        # 创建房间
        self.create_room()
        self.ensure_private()
        self.create_ensure()

        # 邀请队友
        success = True
        is_first = True
        # 这个时候我已经进入房间了哦
        while 1:
            self.screenshot()
            # 无论胜利与否, 都会出现是否邀请一次队友
            # 区别在于，失败的话不会出现那个勾选默认邀请的框
            if self.check_and_invite(self.config.fallen_sun.invite_config.default_invite):
                continue

            # 检查猫咪奖励
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_WIN_3, interval=1):
                continue

            if self.current_count >= self.limit_count:
                if self.is_in_room():
                    logger.info('FallenSun count limit out')
                    break

            if datetime.now() - self.start_time >= self.limit_time:
                if self.is_in_room():
                    logger.info('FallenSun time limit out')
                    break

            # 如果没有进入房间那就不需要后面的邀请
            if not self.is_in_room():
                # 如果在探索界面或者是出现在组队界面， 那就是可能房间死了
                # 要结束任务
                sleep(0.5)
                if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
                    sleep(0.5)
                    if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
                        logger.warning('FallenSun task failed')
                        success = False
                        break
                continue

            # 点击挑战
            if not is_first:
                if self.run_invite(config=self.config.fallen_sun.invite_config):
                    self.run_general_battle(config=self.config.fallen_sun.general_battle_config)
                else:
                    # 邀请失败，退出任务
                    logger.warning('Invite failed and exit this fallen_sun task')
                    success = False
                    break

            # 第一次会邀请队友
            if is_first:
                if not self.run_invite(config=self.config.fallen_sun.invite_config, is_first=True):
                    logger.warning('Invite failed and exit this fallen_sun task')
                    success = False
                    break
                else:
                    is_first = False
                    self.run_general_battle(config=self.config.fallen_sun.general_battle_config)

        # 当结束或者是失败退出循环的时候只有两个UI的可能，在房间或者是在组队界面
        # 如果在房间就退出
        if self.exit_room():
            pass
        # 如果在组队界面就退出
        if self.exit_team():
            pass

        self.ui_get_current_page()
        self.ui_goto(page_main)

        if not success:
            return False
        return True

    def run_member(self):
        logger.info('Start run member')
        self.ui_get_current_page()
        # self.ui_goto(page_soul_zones)
        # self.fallen_sun_enter()
        # self.check_lock(self.config.fallen_sun.general_battle_config.lock_team_enable)

        # 进入战斗流程
        self.device.stuck_record_add('BATTLE_STATUS_S')
        while 1:
            self.screenshot()

            # 检查猫咪奖励
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_WIN_3, interval=1):
                continue

            if self.current_count >= self.limit_count:
                logger.info('FallenSun count limit out')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('FallenSun time limit out')
                break

            if self.check_then_accept():
                continue

            if self.is_in_room():
                self.device.stuck_record_clear()
                if self.wait_battle(wait_time=self.config.fallen_sun.invite_config.wait_time):
                    self.run_general_battle(config=self.config.fallen_sun.general_battle_config)
                else:
                    break
            # 队长秒开的时候，检测是否进入到战斗中
            elif self.check_take_over_battle(False, config=self.config.fallen_sun.general_battle_config):
                continue

        while 1:
            # 有一种情况是本来要退出的，但是队长邀请了进入的战斗的加载界面
            if self.appear(self.I_GI_HOME) or self.appear(self.I_GI_EXPLORE):
                break
            # 如果可能在房间就退出
            if self.exit_room():
                pass
            # 如果还在战斗中，就退出战斗
            if self.exit_battle():
                pass


        self.ui_get_current_page()
        self.ui_goto(page_main)
        return True

    def run_alone(self):
        logger.info('Start run alone')
        self.ui_get_current_page()
        self.ui_goto(page_soul_zones)
        self.fallen_sun_enter()
        layer = self.config.fallen_sun.fallen_sun_config.layer
        self.check_layer(layer)
        self.check_lock(self.config.fallen_sun.general_battle_config.lock_team_enable)

        def is_in_fallen_sun(screenshot=False) -> bool:
            if screenshot:
                self.screenshot()
            return self.appear(self.I_FALLEN_SUN_FIRE)

        while 1:
            self.screenshot()

            # 检查猫咪奖励
            if self.appear_then_click(self.I_PET_PRESENT, action=self.C_WIN_3, interval=1):
                continue

            if not is_in_fallen_sun():
                continue

            if self.current_count >= self.limit_count:
                logger.info('FallenSun count limit out')
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info('FallenSun time limit out')
                break

            # 点击挑战
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_FALLEN_SUN_FIRE, interval=1):
                    pass

                if not self.appear(self.I_FALLEN_SUN_FIRE):
                    self.run_general_battle(config=self.config.fallen_sun.general_battle_config)
                    break

        # 回去
        while 1:
            self.screenshot()
            if not self.appear(self.I_FORM_TEAM):
                break
            if self.appear_then_click(self.I_BACK_BL, interval=1):
                continue

        self.ui_current = page_soul_zones
        self.ui_goto(page_main)

    def run_wild(self):
        logger.error('Wild mode is not implemented')
        pass

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        """
        重写战斗等待
        # https://github.com/runhey/OnmyojiAutoScript/issues/95
        :param random_click_swipt_enable:
        :return:
        """
        # 重写
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        self.C_REWARD_1.name = 'C_REWARD'
        self.C_REWARD_2.name = 'C_REWARD'
        self.C_REWARD_3.name = 'C_REWARD'
        # 战斗过程 随机点击和滑动 防封
        logger.info("Start battle process")
        while 1:
            self.screenshot()
            action_click = random.choice([self.C_WIN_1, self.C_WIN_2, self.C_WIN_3])
            if self.appear_then_click(self.I_WIN, action=action_click ,interval=0.8):
                # 赢的那个鼓
                continue
            if self.appear(self.I_GREED_GHOST):
                # 贪吃鬼
                logger.info('Win battle')
                self.wait_until_appear(self.I_REWARD, wait_time=1.5)
                self.screenshot()
                if not self.appear(self.I_GREED_GHOST):
                    logger.warning('Greedy ghost disappear. Maybe it is a false battle')
                    continue
                while 1:
                    self.screenshot()
                    action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
                    if not self.appear(self.I_GREED_GHOST):
                        break
                    if self.click(action_click, interval=1.5):
                        continue
                return True
            if self.appear(self.I_REWARD):
                # 魂
                logger.info('Win battle')
                while 1:
                    self.screenshot()
                    action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
                    if self.appear_then_click(self.I_REWARD, action=action_click, interval=1.5):
                        continue
                    if not self.appear(self.I_REWARD):
                        break
                return True

            if self.appear(self.I_FALSE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False

            # 如果开启战斗过程随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
    # t.check_layer('日蚀')








