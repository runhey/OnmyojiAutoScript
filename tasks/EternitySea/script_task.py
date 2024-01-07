# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, timedelta

from module.exception import TaskEnd
from module.logger import logger

from tasks.GameUi.game_ui import GameUi, Page
from tasks.GameUi.page import page_soul_zones
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.EternitySea.assets import EternitySeaAssets
from tasks.Orochi.config import UserStatus
from tasks.EternitySea.config import EternitySea
from module.exception import RequestHumanTakeover


class ScriptTask(
    GameUi, GeneralBattle, GeneralRoom, GeneralInvite, SwitchSoul, EternitySeaAssets
):
    @property
    def task_name(self):
        return "EternitySea"

    def run(self) -> None:
        match self._task_config.eternity_sea_config.user_status:
            case UserStatus.ALONE:
                success = self.run_alone()
            case _:
                logger.critical(
                    f"UserStatus {self._task_config.eternity_sea_config.user_status} not support"
                )
                raise RequestHumanTakeover

        if success:
            self.set_next_run(self.task_name, finish=True, success=True)
        else:
            self.set_next_run(self.task_name, finish=False, success=False)

        raise TaskEnd(self.task_name)

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
            if self.appear_then_click(self.I_ETERNITY_SEA, interval=1):
                break

        while True:
            self.screenshot()
            if self.appear(self.I_FORM_TEAM):
                return

    def _navigate_to_soul_zones(self) -> None:
        self.ui_get_current_page()
        self.ui_goto(page_soul_zones)

    def _navigate_to_game_page(self, destination: Page) -> None:
        self.ui_get_current_page()
        self.ui_goto(destination)

    @property
    def _task_config(self) -> EternitySea:
        return self.config.model.eternity_sea


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    c = Config("oas1")
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
