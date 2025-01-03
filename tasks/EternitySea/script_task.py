# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, timedelta

from module.exception import TaskEnd
from module.logger import logger

from tasks.GameUi.game_ui import GameUi, Page
from tasks.GameUi.page import page_soul_zones, page_shikigami_records
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.EternitySea.assets import EternitySeaAssets
from tasks.Orochi.config import UserStatus
from tasks.EternitySea.config import EternitySea
from module.exception import RequestHumanTakeover
from tasks.GameUi.page import page_main, page_soul_zones, page_shikigami_records
from time import sleep

class ScriptTask(
    GameUi, GeneralBattle, GeneralRoom, GeneralInvite, SwitchSoul, EternitySeaAssets
):
    @property
    def task_name(self):
        return "EternitySea"

    def _two_teams_switch_sous(self, config):
        if config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(config.switch_group_team)

        if config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(config.group_name, config.team_name)

    def run(self) -> None:
        self._two_teams_switch_sous(self._task_config.switch_soul_config_1)
        self._two_teams_switch_sous(self._task_config.switch_soul_config_2)
        match self._task_config.eternity_sea_config.user_status:
            case UserStatus.LEADER: success = self.run_leader()
            case UserStatus.MEMBER: success = self.run_member()
            case UserStatus.ALONE: success = self.run_alone()
            case _: logger.error('Unknown user status')

        if success:
            self.set_next_run(self.task_name, finish=True, success=True)
        else:
            self.set_next_run(self.task_name, finish=False, success=False)

        raise TaskEnd(self.task_name)


    def run_leader(self):
        logger.info('Start run leader')
        self._navigate_to_soul_zones()
        self._enter_eternity_sea()
        layer = self._task_config.eternity_sea_config.layer
        self.check_layer(layer)
        self.check_lock(self._task_config.general_battle_config.lock_team_enable)
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
            if self.check_and_invite(self._task_config.invite_config.default_invite):
                continue

            #限制
            if self.current_count >= self._task_config.eternity_sea_config.limit_count:
                logger.info("EternitySea count limit out")
                break
            if datetime.now() - self.start_time >= self._limit_time:
                logger.info("EternitySea time limit out")
                break

            # 如果没有进入房间那就不需要后面的邀请
            if not self.is_in_room():
                if self.is_room_dead():
                    logger.warning('eternity_sea task failed')
                    success = False
                    break
                continue

            # 点击挑战
            if not is_first:
                if self.run_invite(config=self._task_config.invite_config):
                    self.run_general_battle(config=self._task_config.general_battle_config)
                else:
                    # 邀请失败，退出任务
                    logger.warning('Invite failed and exit this eternity_sea task')
                    success = False
                    break

            # 第一次会邀请队友
            if is_first:
                if not self.run_invite(config=self._task_config.invite_config, is_first=True):
                    logger.warning('Invite failed and exit this eternity_sea task')
                    success = False
                    break
                else:
                    is_first = False
                    self.run_general_battle(config=self._task_config.general_battle_config)

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
        # self.orochi_enter()
        # self.check_lock(self.config.orochi.general_battle_config.lock_team_enable)

        # 进入战斗流程
        self.device.stuck_record_add('BATTLE_STATUS_S')
        while 1:
            self.screenshot()

            #限制
            if self.current_count >= self._task_config.eternity_sea_config.limit_count:
                logger.info("EternitySea count limit out")
                break
            if datetime.now() - self.start_time >= self._limit_time:
                logger.info("EternitySea time limit out")
                break

            if self.check_then_accept():
                continue

            if self.is_in_room():
                self.device.stuck_record_clear()
                if self.wait_battle(wait_time=self._task_config.invite_config.wait_time):
                    self.run_general_battle(config=self._task_config.general_battle_config)
                else:
                    break
            # 队长秒开的时候，检测是否进入到战斗中
            elif self.check_take_over_battle(False, config=self._task_config.general_battle_config):
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


    def run_alone(self) -> bool:
        logger.info("Start run alone")
        self._navigate_to_soul_zones()
        self._enter_eternity_sea()

        if self._task_config.general_battle_config.lock_team_enable == False:
            logger.critical(f"Only supports lock team mode")
            raise RequestHumanTakeover

        while 1:
            self.screenshot()

            if not self._is_in_eternity_sea():
                continue

            if self.current_count >= self._task_config.eternity_sea_config.limit_count:
                logger.info("EternitySea count limit out")
                break
            if datetime.now() - self.start_time >= self._limit_time:
                logger.info("EternitySea time limit out")
                break

            # 点击挑战
            while 1:
                self.screenshot()
                if self.appear_then_click(self.I_ETERNITY_SEA_FIRE, interval=1):
                    pass

                if not self.appear(self.I_ETERNITY_SEA_FIRE):
                    self.run_general_battle(
                        config=self._task_config.general_battle_config
                    )
                    break
        return True

    def is_room_dead(self) -> bool:
        # 如果在探索界面或者是出现在组队界面，那就是可能房间死了
        sleep(0.5)
        if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
            sleep(0.5)
            if self.appear(self.I_MATCHING) or self.appear(self.I_CHECK_EXPLORATION):
                return True
        return False

    def eternitysea_enter(self) -> bool:
        logger.info('Enter EternitySea')
        while True:
            self.screenshot()
            if self.appear(self.I_FORM_TEAM):
                return True
            if self.appear_then_click(self.I_ETERNITY_SEA, interval=1):
                continue


    def _is_in_eternity_sea(self) -> bool:
        self.screenshot()
        return self.appear(self.I_ETERNITY_SEA_FIRE)

    @property
    def _limit_time(self) -> timedelta:
        limit_time = self._task_config.eternity_sea_config.limit_time
        return timedelta(
            hours=limit_time.hour, minutes=limit_time.minute, seconds=limit_time.second
        )

    def _enter_eternity_sea(self) -> None:
        logger.info("Enter eternity_sea")
        while True:
            self.screenshot()
            if self.appear(self.I_FORM_TEAM, interval=1):
                return True
            if self.appear_then_click(self.I_ETERNITY_SEA, interval=1):
                continue
            #有可能点击到录像
            if self.appear_then_click(self.I_BACK_BOTTOM, interval=1):
                continue

    def _navigate_to_soul_zones(self) -> None:
        self.ui_get_current_page()
        self.ui_goto(page_soul_zones)

    def _navigate_to_game_page(self, destination: Page) -> None:
        self.ui_get_current_page()
        self.ui_goto(destination)

    @property
    def _task_config(self) -> EternitySea:
        return self.config.model.eternity_sea

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
        检查是否锁定阵容, 要求在永生之海界面
        :param lock:
        :return:
        """
        logger.info('Check lock: %s', lock)
        if lock:
            while 1:
                self.screenshot()
                if self.appear(self.I_NEWETERNITYSEA_LOCK):
                    return True
                if self.appear_then_click(self.I_ETERNITYSEA_UNLOCK, interval=1):
                    continue
        else:
            while 1:
                self.screenshot()
                if self.appear(self.I_ETERNITYSEA_UNLOCK):
                    return True
                if self.appear_then_click(self.I_NEWETERNITYSEA_LOCK, interval=1):
                    continue

if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    c = Config("oas1")
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()