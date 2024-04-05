# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Exploration.assets import ExplorationAssets
from tasks.Exploration.config import ChooseRarity, AutoRotate, AttackNumber
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_exploration, page_shikigami_records, page_main

from module.logger import logger
from module.exception import RequestHumanTakeover, TaskEnd
from module.atom.image_grid import ImageGrid


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, ExplorationAssets):
    medal_grid: ImageGrid = None

    def run(self):
        """
        执行
        :return:
        """
        # 探索的 config
        explorationConfig = self.config.exploration

        # 切换御魂
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
        if con.buff_gold_50_click or con.buff_gold_100_click:
            self.ui_get_current_page()
            self.ui_goto(page_main)
            self.open_buff()
            if con.buff_gold_50_click:
                self.gold_50()
            if con.buff_gold_100_click:
                self.gold_100()
            self.close_buff()

        self.ui_get_current_page()
        # 探索页面
        self.ui_goto(page_exploration)

        # ************************* 跳转至对应指定章节并进入 *******************
        # 默认全部解锁， 当前处于第二十八章
        # 查找指定的章节：
        if not self.open_expect_level():
            logger.critical(f'Not find {explorationConfig.exploration_config.exploration_level} or'
                            f' Enter {explorationConfig.exploration_config.exploration_level} failed!')
            raise RequestHumanTakeover

        # 只探索7次
        if explorationConfig.exploration_config.attack_number == AttackNumber.SEVEN:
            count = 0
            while count < 7:
                if self.wait_until_appear(self.I_E_EXPLORATION_CLICK, wait_time=1):
                    self.click(self.I_E_EXPLORATION_CLICK)
                    count += 1
                    # 进入战斗环节
                    self.battle_process()
                if self.appear(self.I_EXPLORATION_TITLE):
                    self.open_expect_level()

            if self.wait_until_appear(self.I_RED_CLOSE, wait_time=2):
                self.appear_then_click(self.I_RED_CLOSE)
            self.ui_goto(page_main)
            self.set_next_run(task='Exploration', success=True, finish=False)
        raise TaskEnd

    # 查找指定的章节：
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
            self.device.click_record_clear()
            self.swipe(self.S_SWIPE_LEVEL_UP)
            swipeCount += 1
            if swipeCount >= 25:
                return False

        # 选中对应章节
        while 1:
            self.screenshot()
            self.O_E_EXPLORATION_LEVEL_NUMBER.keyword = explorationConfig.exploration_config.exploration_level
            if self.ocr_appear_click(self.O_E_EXPLORATION_LEVEL_NUMBER):
                self.wait_until_appear(self.I_E_EXPLORATION_CLICK, wait_time=3)
            if self.appear(self.I_E_EXPLORATION_CLICK):
                break

        return True

    # 候补：
    def enter_settings_and_do_operations(self):
        # 打开设置
        self.click(self.C_CLICK_SETTINGS)
        while 1:
            self.screenshot()
            if self.appear(self.I_E_OPEN_SETTINGS):
                break
            else:
                self.click(self.C_CLICK_SETTINGS)
                if self.wait_until_appear(self.I_E_OPEN_SETTINGS):
                    break
        # 候补出战数量识别
        self.screenshot()
        cu, res, total = self.O_E_ALTERNATE_NUMBER.ocr(self.device.image)
        if cu >= 40:
            self.appear_then_click(self.I_E_SURE_BUTTON)
            return
        else:
            self.add_shiki()

    # 添加式神
    def add_shiki(self):
        self.screenshot()
        # 点击展开式神稀有度选择界面
        self.click(self.C_CLICK_ALL_SHIKI)
        while 1:
            self.screenshot()
            # 成功进入稀有度选择界面
            if self.appear(self.I_E_ENTER_CHOOSE_RARITY):
                if self.config.exploration.exploration_config.choose_rarity == ChooseRarity.N:
                    # N 卡
                    self.click(self.C_CLICK_N_SHIKI)
                else:
                    # 素材卡
                    self.appear_then_click(self.I_E_ENTER_CHOOSE_RARITY)
            self.screenshot()
            if self.appear(self.I_E_N_RARITY):
                # 进入N卡添加界面  退出
                break
            if self.appear(self.I_E_S_RARITY):
                # 进入素材添加界面 退出
                break
        # 选中候补出战框
        self.click(self.C_CLICK_STANDBY_TEAM)
        # 移动至未候补的狗粮
        while 1:
            # 慢一点
            time.sleep(0.5)
            self.screenshot()
            if self.appear(self.I_E_RATATE_EXSIT):
                self.swipe(self.S_SWIPE_SHIKI_TO_LEFT)
            else:
                break
        while 1:
            # 候补出战数量识别
            self.screenshot()
            cu, res, total = self.O_E_ALTERNATE_NUMBER.ocr(self.device.image)
            if cu >= 40:
                break
            self.swipe(self.S_SWIPE_SHIKI_TO_LEFT_ONE)
            # 慢一点
            time.sleep(0.5)
            self.screenshot()
            self.click(self.C_CLICK_ROTATE_1)
            self.device.click_record_clear()

        self.appear_then_click(self.I_E_SURE_BUTTON)

    # 探索战斗流程
    def do_battle(self):
        while 1:
            self.screenshot()
            # 战后奖励
            if self.appear(self.I_BATTLE_REWARD) and not self.appear(self.I_GET_REWARD):
                self.click(self.I_BATTLE_REWARD)
            # boss 战
            if self.appear_then_click(self.I_BOSS_BATTLE_BUTTON):
                if self.wait_until_appear(self.I_BATTLE_START, wait_time=5):
                    self.run_general_battle(self.config.exploration.general_battle_config)
                else:
                    continue
            # 小怪 战
            if self.appear_then_click(self.I_NORMAL_BATTLE_BUTTON):
                if self.wait_until_appear(self.I_BATTLE_START, wait_time=5):
                    self.run_general_battle(self.config.exploration.general_battle_config)
                else:
                    continue
            # 滑动
            elif self.appear(self.I_E_AUTO_ROTATE_ON) or self.appear(self.I_GET_REWARD):
                self.swipe(self.S_SWIPE_BACKGROUND_RIGHT)
            # 结束流程
            if self.appear(self.I_E_EXPLORATION_CLICK) or self.appear(self.I_EXPLORATION_TITLE):
                break

    # 战斗流程
    def battle_process(self):
        # 进入指定章节
        self.screenshot()
        if self.appear_then_click(self.I_E_EXPLORATION_CLICK):
            self.appear_then_click(self.I_E_SETTINGS_BUTTON)

        # ************************* 进入设置并操作 *******************
        # 候补以及自动轮换打开：
        # 自动轮换功能打开
        while 1:
            self.screenshot()
            # 自动轮换开着 则跳过
            if self.appear(self.I_E_AUTO_ROTATE_ON):
                break
            # 自动轮换关着 则打开
            if self.appear_then_click(self.I_E_AUTO_ROTATE_OFF):
                if self.appear(self.I_E_AUTO_ROTATE_ON):
                    break

        # 自动添加候补式神
        if self.config.exploration.exploration_config.auto_rotate == AutoRotate.yes:
            self.enter_settings_and_do_operations()
        
        # 修复卡结算问题
        # 卡结算是因为没有设置锁定队伍，修改后无论是否锁定都不会因为没有锁定队伍而卡在结算界面
        if not self.config.exploration.general_battle_config.lock_team_enable:
            self.config.exploration.general_battle_config.lock_team_enable = True

        # 进入战斗环节
        self.do_battle()


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas2')
    device = Device(config)
    t = ScriptTask(config, device)
    t.config.exploration.exploration_config.exploration_level = '第二十八章'
    t.run()
    # t.battle_process()
    # t.enter_settings_and_do_operations()
