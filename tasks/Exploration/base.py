# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
import numpy as np
import random
from enum import Enum
from cached_property import cached_property
from datetime import timedelta, datetime

from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.ReplaceShikigami.replace_shikigami import ReplaceShikigami
from tasks.Exploration.assets import ExplorationAssets
from tasks.Exploration.config import ChooseRarity, AutoRotate, AttackNumber, UpType
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_exploration, page_shikigami_records, page_main
from tasks.RealmRaid.script_task import ScriptTask as RealmRaidScriptTask
from tasks.Utils.config_enum import ShikigamiClass

from module.logger import logger
from module.exception import RequestHumanTakeover, TaskEnd
from module.atom.image_grid import ImageGrid
from module.base.utils import load_image

class Scene(Enum):
    UNKNOWN = 0  #
    WORLD = 1  # 探索大世界
    ENTRANCE = 2  # 入口弹窗
    MAIN = 3  # 探索里面
    BATTLE_PREPARE = 4  # 战斗准备
    BATTLE_FIGHTING = 5  # 战斗中
    TEAM = 6  # 组队




class BaseExploration(GameUi, GeneralBattle, GeneralRoom, GeneralInvite, ReplaceShikigami, SwitchSoul, ExplorationAssets):
    minions_cnt = 0

    @cached_property
    def _config(self):
        self.config.exploration.general_battle_config.lock_team_enable = True
        limit_time = self.config.exploration.exploration_config.limit_time
        self.limit_time: timedelta = timedelta(
            hours=limit_time.hour,
            minutes=limit_time.minute,
            seconds=limit_time.second
        )
        return self.config.model.exploration

    def get_current_scene(self, reuse_screenshot: bool = True) -> Scene:
        if not reuse_screenshot:
            self.screenshot()

        if self.appear(self.I_CHECK_EXPLORATION) and not self.appear(self.I_E_SETTINGS_BUTTON):
            return Scene.WORLD
        elif self.appear(self.I_UI_BACK_RED) and self.appear(self.I_E_EXPLORATION_CLICK):
            return Scene.ENTRANCE
        elif self.appear(self.I_E_SETTINGS_BUTTON) or self.appear(self.I_E_AUTO_ROTATE_ON) or self.appear(self.I_E_AUTO_ROTATE_OFF):
            return Scene.MAIN
        elif self.is_in_prepare():
            return Scene.BATTLE_PREPARE
        elif self.is_in_battle():
            return Scene.BATTLE_FIGHTING
        elif self.is_in_room() or self.appear(self.I_CREATE_ENSURE):
            return Scene.TEAM

        logger.info("Unknown scene")
        return Scene.UNKNOWN

    def pre_process(self):
        explorationConfig = self._config
        if explorationConfig.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(explorationConfig.switch_soul_config.switch_group_team)

        if explorationConfig.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(explorationConfig.switch_soul_config.group_name,
                                         explorationConfig.switch_soul_config.team_name)

        # 开启加成
        con = self.config.exploration.exploration_config
        if con.buff_gold_50_click or con.buff_gold_100_click or con.buff_exp_50_click or con.buff_exp_100_click:
            self.ui_get_current_page()
            self.ui_goto(page_main)
            self.open_buff()
            if con.buff_gold_50_click:
                self.gold_50()
            if con.buff_gold_100_click:
                self.gold_100()
            if con.buff_exp_50_click:
                self.exp_50()
            if con.buff_exp_100_click:
                self.exp_100()
            self.close_buff()

        self.ui_get_current_page()
        # 探索页面
        self.ui_goto(page_exploration)

    def post_process(self):
        self.ui_get_current_page()
        self.ui_goto(page_main)
        con = self._config.exploration_config
        if con.buff_gold_50_click or con.buff_gold_100_click or con.buff_exp_50_click or con.buff_exp_100_click:
            self.open_buff()
            self.gold_50(is_open=False)
            self.gold_100(is_open=False)
            self.exp_50(is_open=False)
            self.exp_100(is_open=False)
            self.close_buff()
        self.set_next_run(task='Exploration', success=True, finish=False)
        raise TaskEnd

    # 打开指定的章节：
    def open_expect_level(self):
        swipeCount = 0
        while 1:
            # 探索的 config
            explorationConfig = self.config.exploration

            # 判断有无目标章节
            self.screenshot()
            # 获取当前章节名
            results = self.O_E_EXPLORATION_LEVEL_NUMBER.detect_and_ocr(self.device.image)
            text1 = [result.ocr_text for result in results]
            # 判断当前章节有无目标章节
            result = set(text1).intersection({explorationConfig.exploration_config.exploration_level})
            # 有则跳出检测
            if self.appear(self.I_E_EXPLORATION_CLICK) or result and len(result) > 0:
                break
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                continue
            self.device.click_record_clear()
            self.swipe(self.S_SWIPE_LEVEL_UP)
            swipeCount += 1
            if swipeCount >= 25:
                return False

        # 选中对应章节
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                continue
            self.O_E_EXPLORATION_LEVEL_NUMBER.keyword = explorationConfig.exploration_config.exploration_level
            if self.ocr_appear_click(self.O_E_EXPLORATION_LEVEL_NUMBER):
                self.wait_until_appear(self.I_E_EXPLORATION_CLICK, wait_time=3)
            if self.appear(self.I_E_EXPLORATION_CLICK):
                break
            if self.is_in_room():
                break

        return True

    # 候补：
    def enter_settings_and_do_operations(self):
        # 打开设置
        while 1:
            self.screenshot()
            if self.appear(self.I_E_OPEN_SETTINGS):
                logger.info("Open settings")
                break
            if self.is_in_battle():
                logger.warning('Opening settings failed due to now in battle')
                return
            if self.click(self.C_CLICK_SETTINGS, interval=2):
                continue

        # 候补出战数量识别
        self.screenshot()
        if not self.appear(self.I_E_OPEN_SETTINGS):
            logger.warning('Opening settings failed due to now in battle')
            return
        cu, res, total = self.O_E_ALTERNATE_NUMBER.ocr(self.device.image)
        if cu >= 10:
            logger.info("Alternate number is enough")
            self.ui_click_until_disappear(self.I_E_SURE_BUTTON)
            return
        else:
            self.add_shiki()

    # 添加式神
    def add_shiki(self, screenshot=True):
        if screenshot:
            self.screenshot()
            if not self.appear(self.I_E_OPEN_SETTINGS):
                logger.warning('Opening settings failed due to now in battle')
                return
        choose_rarity = self._config.exploration_config.choose_rarity
        rarity = ShikigamiClass.N if choose_rarity == ChooseRarity.N else ShikigamiClass.MATERIAL
        self.switch_shikigami_class(rarity)

        self.click(self.C_CLICK_STANDBY_TEAM)
        # 移动至未候补的狗粮
        while 1:
            # 慢一点
            time.sleep(0.5)
            self.screenshot()
            if not self.appear(self.I_E_OPEN_SETTINGS):
                logger.warning('Opening settings failed due to now in battle')
                return
            if self.appear(self.I_E_RATATE_EXSIT):
                self.swipe(self.S_SWIPE_SHIKI_TO_LEFT)
            else:
                break
        while 1:
            # 候补出战数量识别
            self.screenshot()
            if not self.appear(self.I_E_OPEN_SETTINGS):
                logger.warning('Opening settings failed due to now in battle')
                return
            cu, res, total = self.O_E_ALTERNATE_NUMBER.ocr(self.device.image)
            if cu >= 40:
                break
            self.swipe(self.S_SWIPE_SHIKI_TO_LEFT_ONE)
            # 慢一点
            time.sleep(0.5)
            self.screenshot()
            self.click(self.L_ROTATE_1)
            self.device.click_record_clear()

        self.appear_then_click(self.I_E_SURE_BUTTON)

    # 找up按钮
    def search_up_fight(self, up_type: UpType = None):
        if up_type is None:
            up_type = self._config.exploration_config.up_type
        if up_type != UpType.ALL:
            match up_type:
                case UpType.EXP:
                    find_flag = self.I_UP_EXP
                case UpType.COIN:
                    find_flag = self.I_UP_COIN
                case UpType.DARUMAA:
                    find_flag = self.I_UP_DARUMA
                case _:
                    find_flag = self.I_UP_EXP
            appear = self.appear(find_flag)
            if not appear:
                return None
            logger.info(f'Found up type: {up_type} at  {find_flag.roi_front}')
            x, y, _, _ = find_flag.roi_front
            x_center, y_center = find_flag.front_center()
            roi_back_y = max(0, y - 300)
            roi_back_h = y - 20 - roi_back_y
            roi_back_x = max(0, x - 160)
            roi_back_w = min(1280, x + 200) - roi_back_x
            # self.I_NORMAL_BATTLE_BUTTON.roi_back = [roi_back_x, roi_back_y, roi_back_w, roi_back_h]
            logger.info(f'It will search normal battle button at {roi_back_x, roi_back_y, roi_back_w, roi_back_h}')
            matches = self.I_NORMAL_BATTLE_BUTTON.match_all(
                image=self.device.image,
                threshold=0.9,
                roi=[roi_back_x, roi_back_y, roi_back_w, roi_back_h]
            )
            if not matches:
                return None
            distances = []
            for match in matches:
                x_match, y_match = match[1], match[2]
                distance = np.linalg.norm(
                    np.array([x_center, y_center]) - np.array([x_match, y_match])
                )
                distances.append((distance, match))
            distances.sort(key=lambda x: x[0], reverse=False)
            match = distances[0][1]
            roi_front = list(match[1:])  # x,y,w,h
            self.I_NORMAL_BATTLE_BUTTON.roi_front = roi_front
            logger.info(f"Found normal battle button at {roi_front}")
            return self.I_NORMAL_BATTLE_BUTTON
        if self.appear(self.I_NORMAL_BATTLE_BUTTON):
            return self.I_NORMAL_BATTLE_BUTTON
        return None

    def activate_realm_raid(self, con_scrolls, con) -> None:
        # 判断是否开启突破票检测
        if not con_scrolls.scrolls_enable:
            return
        if self.appear(self.I_E_EXPLORATION_CLICK) and self.appear(self.I_EXP_CREATE_TEAM):
            cu, res, total = self.O_REALM_RAID_NUMBER1.ocr(self.device.image)
        else:
            cu, res, total = self.O_REALM_RAID_NUMBER.ocr(self.device.image)
        # 判断突破票数量
        if cu < con_scrolls.scrolls_threshold:
            return

        # 关闭加成
        if self.appear(self.I_RED_CLOSE):
            self.ui_click_until_disappear(self.I_RED_CLOSE)
        if self.appear(self.I_UI_CANCEL):
            self.ui_click_until_disappear(self.I_UI_CANCEL)
        if self.appear(self.I_UI_CANCEL_SAMLL):
            self.ui_click_until_disappear(self.I_UI_CANCEL_SAMLL)
        self.ui_goto(page_main)
        if con.buff_gold_50_click or con.buff_gold_100_click or con.buff_exp_50_click or con.buff_exp_100_click:
            self.open_buff()
            self.gold_50(is_open=False)
            self.gold_100(is_open=False)
            self.exp_50(is_open=False)
            self.exp_100(is_open=False)
            self.close_buff()

        # 设置下次执行行时间
        logger.info("RealmRaid and Exploration  set_next_run !")
        next_run = datetime.now() + con_scrolls.scrolls_cd
        self.set_next_run(task='Exploration', success=False, finish=False, target=next_run)
        self.set_next_run(task='RealmRaid', success=False, finish=False, target=datetime.now())
        raise TaskEnd

    #
    def check_exit(self) -> bool:
        # True 表示要退出这个任务
        if self.minions_cnt >= self._config.exploration_config.minions_cnt:
            logger.info('Minions count is enough, exit')
            return True
        if datetime.now() - self.start_time >= self.limit_time:
            logger.info('Exploration time limit out')
            return True
        self.activate_realm_raid(self._config.scrolls, self._config.exploration_config)
        return False

    def quit_explore(self):
        logger.info('Quit explore')
        while 1:
            self.screenshot()
            if self.appear(self.I_UI_BACK_RED) and self.appear(self.I_E_EXPLORATION_CLICK):
                break
            if self.appear_then_click(self.I_E_EXIT_CONFIRM, interval=0.8):
                continue
            if self.appear_then_click(self.I_UI_BACK_BLUE, interval=1.5):
                continue

    def fire(self, button) -> bool:
        self.ui_click_until_disappear(button, interval=3)
        self.screenshot()
        if (self.appear(self.I_E_SETTINGS_BUTTON) or
                self.appear(self.I_E_AUTO_ROTATE_ON) or
                self.appear(self.I_E_AUTO_ROTATE_OFF)):
            # 如果还在探索说明，这个是显示滑动导致挑战按钮不在范围内
            logger.warning('Fire button disappear, but still in exploration')
            return False
        self.run_general_battle(self._config.general_battle_config)
        self.minions_cnt += 1
        return True


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas1')
    device = Device(config)
    t = BaseExploration(config, device)
    t.screenshot()

    # IMAGE_FILE = r"C:\Users\萌萌哒\Desktop\QQ20240818-163854.png"
    # image = load_image(IMAGE_FILE)
    # t.device.image = image
    while 1:
    # print(t.search_up_fight(UpType.EXP))
        t.screenshot()
        print(t.I_UP_DARUMA.test_match(t.device.image))
        time.sleep(0.2)
    from PIL import Image
    # Image.fromarray(t.device.image.astype(np.uint8)).show()

