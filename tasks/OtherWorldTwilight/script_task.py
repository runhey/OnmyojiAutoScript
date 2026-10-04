# This Python file uses the following encoding: utf-8
# @author AzurTian
from time import sleep
from datetime import datetime

from module.base.timer import Timer

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from module.logger import logger
from module.exception import TaskEnd
from tasks.GameUi.page import (
    page_main, page_battle, page_battle_prepare, page_reward, page_shikigami_records,
)
from tasks.OtherWorldTwilight.assets import OtherWorldTwilightAssets
from tasks.OtherWorldTwilight.page import page_owt
from tasks.OtherWorldTwilight.config import OtherWorldTwilight
from tasks.Orochi.config import UserStatus


class ScriptTask(GeneralBattle, GeneralInvite, GeneralRoom, GameUi, SwitchSoul, OtherWorldTwilightAssets):

    conf: OtherWorldTwilight = None

    def run(self) -> bool:
        self.conf = self.config.other_world_twilight
        if self.conf.switch_soul.enable:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(self.conf.switch_soul.switch_group_team)
        if self.conf.switch_soul.enable_switch_by_name:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul_by_name(self.conf.switch_soul.group_name, self.conf.switch_soul.team_name)
        success = True
        match self.conf.other_world_twilight_config.user_status:
            case UserStatus.LEADER: success = self.run_leader()
            case UserStatus.MEMBER: success = self.run_member()
            case UserStatus.ALONE: self.run_alone()
            case _: logger.error('Unknown user status')
        self.goto_page(page_main)
        if success:
            self.set_next_run('OtherWorldTwilight', finish=True, success=True)
        else:
            self.set_next_run('OtherWorldTwilight', finish=True, success=False)
        raise TaskEnd('OtherWorldTwilight')

    def run_leader(self):
        logger.info('Start run leader')
        self.goto_page(page_owt)
        self.check_lock(self.conf.general_battle_config.lock_team_enable, self.I_OWT_LOCK, self.I_OWT_UNLOCK)
        # 创建队伍
        logger.info('Create team')
        self.ui_click(self.I_OWT_TEAM, self.I_CHECK_TEAM, interval=1)
        # 创建房间
        if not self.create_room():
            logger.warning('Create room failed')
            return False
        self.ensure_private()
        if not self.create_ensure():
            logger.warning('Create ensure failed')
            return False
        # 邀请队友
        success = True
        is_first = True
        # 这个时候我已经进入房间了哦
        while 1:
            self.screenshot()
            # 无论胜利与否, 都会出现是否邀请一次队友
            # 区别在于，失败的话不会出现那个勾选默认邀请的框
            if self.check_and_invite(self.conf.invite_config.default_invite):
                continue
            if self.current_count >= self.conf.other_world_twilight_config.limit_count:
                if self.is_in_room():
                    logger.info('Count limit out')
                    break
            if datetime.now() - self.start_time >= self.conf.other_world_twilight_config.limit_time_v:
                if self.is_in_room():
                    logger.info('Time limit out')
                    break
            # 如果没有进入房间那就不需要后面的邀请
            if not self.is_in_room(False):
                if self.is_room_dead():
                    logger.warning('Task failed')
                    success = False
                    break
                continue
            # 点击挑战
            if not is_first:
                if self.run_invite(config=self.conf.invite_config):
                    self.run_general_battle(config=self.conf.general_battle_config)
                else:
                    # 邀请失败，退出任务
                    logger.warning('Invite failed and exit this task')
                    success = False
                    break
            # 第一次会邀请队友
            if is_first:
                if not self.run_invite(config=self.conf.invite_config, is_first=True):
                    logger.warning('Invite failed and exit this task')
                    success = False
                    break
                else:
                    is_first = False
                    self.run_general_battle(config=self.conf.general_battle_config)

        # 当结束或者是失败退出循环的时候只有两个UI的可能，在房间或者是在组队界面
        # 两者都是幂等的，不在对应界面时直接返回
        self.exit_room()
        self.exit_team()
        return success

    def run_member(self):
        logger.info('Start run member')
        self.goto_page(page_main)
        # 进入战斗流程
        self.device.stuck_record_add('BATTLE_STATUS_S')
        while 1:
            self.screenshot()
            if self.current_count >= self.conf.other_world_twilight_config.limit_count:
                logger.info('Count limit out')
                break
            if datetime.now() - self.start_time >= self.conf.other_world_twilight_config.limit_time_v:
                logger.info('Time limit out')
                break
            if self.check_then_accept():
                continue
            if self.is_in_room(False):
                self.device.stuck_record_clear()
                if self.wait_battle(wait_time=self.conf.invite_config.wait_time):
                    self.run_general_battle(config=self.conf.general_battle_config)
                else:
                    break
            # 队长秒开的时候，检测是否加入到战斗中
            if self.is_in_battle(False):
                self.run_general_battle(config=self.conf.general_battle_config)

        # 有一种情况是本来要退出的，但是队长邀请了进入的战斗的加载界面
        while 1:
            if self.appear(self.I_CHECK_MAIN) or self.appear(self.I_OWT_FIRE):
                break
            # 可能在房间就退出，可能还在战斗中就退出战斗，两者都是幂等的
            self.exit_room()
            self.exit_battle()
        return True

    def run_alone(self):
        logger.info('Start run alone')
        self.goto_page(page_owt)
        self.check_lock(self.conf.general_battle_config.lock_team_enable, self.I_OWT_LOCK, self.I_OWT_UNLOCK)
        unknown_page_timer = Timer(10)
        while 1:
            if self.current_count >= self.conf.other_world_twilight_config.limit_count:
                logger.info('Count limit out')
                break
            if datetime.now() - self.start_time >= self.conf.other_world_twilight_config.limit_time_v:
                logger.info('Time limit out')
                break
            self.screenshot()
            current_page = self.get_current_page(False)
            # session 返回的 Page 是 clone，与模块级 page_owt 不是同一对象，
            # 必须用 == （Page.__eq__ 比 key），is 恒为 False
            if current_page is None:
                sleep(0.5)
            elif current_page == page_owt:
                unknown_page_timer.clear()
                self.appear_then_click(self.I_OWT_FIRE, interval=1.2)
            elif current_page in (page_battle_prepare, page_battle, page_reward):
                unknown_page_timer.clear()
                self.run_general_battle(self.conf.general_battle_config)
            else:
                # 未知页面, 可能是从别处进来的, 超时后拉回彼世逢魔页面
                if not unknown_page_timer.started():
                    unknown_page_timer.start()
                elif unknown_page_timer.reached():
                    logger.warning(f'Unknown page: {current_page}, goto page_owt')
                    self.goto_page(page_owt)
                    unknown_page_timer.clear()

    def is_room_dead(self) -> bool:
        # 如果在探索界面或者是出现在组队界面，那就是可能房间死了
        sleep(0.5)
        if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
            sleep(0.5)
            if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
                return True
        return False


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
