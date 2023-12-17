# This Python file uses the following encoding: utf-8

import time
from module.exception import TaskEnd
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_exploration
from tasks.DevExploration.assets import DevExplorationAssets
from module.logger import logger
from tasks.Secret.assets import SecretAssets
from tasks.DevExploration.config import ExplorationMode


class ScriptTask(GeneralBattle, GameUi, DevExplorationAssets):

    def run(self):
        options = self.config.dev_exploration
        if options.exploration_config.mode == ExplorationMode.CAPTAIN:
            return self._run_captain()
        elif options.exploration_config.mode == ExplorationMode.MEMBER:
            return self._run_member()
        else:
            logger.exception("Invalid mode, please choice [captain] or [member]")
        self._run_member()

    def _run_captain(self):
        options = self.config.dev_exploration
        self.ui_get_current_page()
        self.ui_goto(page_exploration)

        while True:
            self.screenshot()
            if self.ocr_appear(self.O_TEAM_BUTTON):
                break
            if self.appear_then_click(self.I_CHAPTER, interval=2):
                continue

        while True:
            self.screenshot()
            if self.ocr_appear(self.O_CREATE_BUTTON):
                break
            if self.ocr_appear_click(self.O_TEAM_BUTTON, interval=2):
                continue

        while True:
            self.screenshot()
            if self.appear(self.I_SMILE):
                break
            if self.ocr_appear_click(self.O_CREATE_BUTTON, interval=2):
                continue

        while True:
            self.screenshot()
            if self.ocr_appear(self.O_INVITE):
                break
            if self.click(self.C_ADD_AREA, interval=2):
                continue

        friend_name = options.exploration_config.friend
        logger.info("准备邀请队员：%s" % friend_name)
        self.O_FRIEND.keyword = friend_name

        time.sleep(2)
        self.screenshot()
        if not self.ocr_appear_click(self.O_FRIEND):
            logger.error("无法找到队员：%s" % friend_name)
            raise TaskEnd

        time.sleep(2)
        self.screenshot()
        self.ocr_appear_click(self.O_INVITE)
        self.wait_until_disappear(self.I_ADD_IMAGE)

        # 进入探索
        self.appear_then_click(self.I_START)
        time.sleep(3)

        while True:
            self.screenshot()
            if self.in_fight():
                logger.info("检测到进入战斗")
                self.battle_wait(random_click_swipt_enable=False)
            if self.in_room():
                self.wait_until_disappear(self.I_ADD_IMAGE)
                self.appear_then_click(self.I_START)
            if self.ocr_appear_click(self.O_QUEREN):
                pass
            if self.ocr_appear_click(self.O_QUEDING):
                pass
            time.sleep(0.2)

    def _run_member(self):
        count = 0
        while True:
            self.screenshot()
            if self.appear_then_click(self.I_ACCEPT):
                time.sleep(2)
            if self.in_fight():
                count += 1
                logger.info("检测到进入战斗 %s" % str(count))
                self.battle_wait(random_click_swipt_enable=False)
            if self.appear(self.I_EXIT_SIGN) or self.appear(self.I_EXIT_SIGN_2):
                self.appear_then_click(self.I_EXIT_TANSUO)
            if self.ocr_appear_click(self.O_QUEREN_2):
                pass
            time.sleep(0.2)

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 重写
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        # 战斗过程 随机点击和滑动 防封
        logger.info("Start battle process")
        while 1:
            self.screenshot()
            if self.appear(SecretAssets.I_SE_BATTLE_WIN):
                logger.info('Win battle')
                self.ui_click_until_disappear(SecretAssets.I_SE_BATTLE_WIN)
                return True
            if self.appear_then_click(self.I_WIN, interval=1):
                continue
            if self.appear(self.I_REWARD):
                logger.info('Win battle')
                self.ui_click_until_disappear(self.I_REWARD)
                return True

            if self.appear(self.I_FALSE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_FALSE)
                return False

    def in_fight(self):
        self.screenshot()
        if self.appear(self.I_EXIT):
            return True
        else:
            return False

    def in_room(self):
        self.screenshot()
        if self.appear(self.I_SMILE):
            return True
        else:
            return False


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas2')
    device = Device(config)
    t = ScriptTask(config, device)
    t.run()
