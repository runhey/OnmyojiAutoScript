# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, timedelta, time
import random  # type: ignore

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.HeroTest.assets import HeroTestAssets
from tasks.GameUi.game_ui import GameUi
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul

from module.logger import logger
from module.exception import TaskEnd
from tasks.HeroTest.config import Layer, HeroTest
from typing import Callable

import tasks.GameUi.page as pages


class ScriptTask(GameUi, GeneralBattle, HeroTestAssets, SwitchSoul):

    conf: HeroTest
    page_hero_mode: pages.Page  # 当前英杰对应模式界面(经验or技能)
    is_skill: bool = False

    def run(self) -> None:
        self.conf = self.config.hero_test
        self.limit_time: timedelta = self.conf.herotest.limit_time
        if isinstance(self.limit_time, time):
            self.limit_time = timedelta(
                hours=self.limit_time.hour,
                minutes=self.limit_time.minute,
                seconds=self.limit_time.second,
            )
        self.limit_count = self.conf.herotest.limit_count
        self.check_and_switch_soul()
        self.open_exp_buff()
        self.switch_hero(self.conf.herotest.layer)
        self.init_pages()
        self.ui_goto_page(self.page_hero_mode)
        self.check_and_lock_team()
        while True:
            if self.limit_time is not None and self.limit_time + self.start_time < datetime.now():
                logger.info("Time out")
                break
            if self.current_count >= self.limit_count:
                logger.info("Count out")
                break
            self.ui_goto_page(self.page_hero_mode)
            if not self.can_run(self.conf.herotest.layer):
                break
            self.enter_battle()
            if self.run_general_battle(config=self.conf.general_battle):
                logger.info("General battle success")
        self.close_exp_buff()
        self.set_next_run(task="HeroTest", success=True)
        raise TaskEnd

    def enter_battle(self):
        """进入战斗"""
        logger.info("Click battle")
        while True:
            self.screenshot()
            if self.is_in_battle(False):
                break  # 在战斗中则跳出循环
            if self.appear_then_click(self.I_START_CHALLENGE, interval=1):  # 兵藏秘境确认挑战
                continue
            if self.appear_then_click(self.I_BCMJ_RESET_CONFIRM, interval=1):  # 兵藏秘境确认重置
                continue
            if self.appear_then_click(self.O_FIRE, interval=1.6):  # 挑战按钮
                self.device.stuck_record_clear()
                continue

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        self.device.stuck_record_add("BATTLE_STATUS_S")
        self.device.click_record_clear()
        logger.info("Start battle process")
        win: bool = False
        while 1:
            self.screenshot()
            if self.appear(self.I_WIN, threshold=0.8) or self.appear(self.I_DE_WIN):
                logger.info("Battle result is win")
                if self.appear(self.I_DE_WIN):
                    self.ui_click_until_disappear(self.I_DE_WIN)
                win = True
                break

            # 如果出现失败 就点击，返回False
            if self.appear(self.I_FALSE, threshold=0.8):
                logger.info("Battle result is false")
                win = False
                break

            # 如果领奖励
            if self.appear(self.I_REWARD, threshold=0.6):
                win = True
                break

            # 如果领奖励出现金币
            if self.appear(self.I_REWARD_GOLD, threshold=0.8):
                win = True
                break
            # 如果开启战斗过程随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()

        # 再次确认战斗结果
        logger.info("Reconfirm the results of the battle")
        while 1:
            self.screenshot()
            if win:
                # 点击赢了
                # self.C_WIN_2 在掉落物品过多的时候可能会点击到物品，导致脚本卡死
                action_click = random.choice([self.C_WIN_1, self.C_WIN_3])
                if self.appear_then_click(
                    self.I_WIN, action=action_click, interval=0.5
                ):
                    continue
                if not self.appear(self.I_WIN):
                    break
            else:
                # 如果失败且 点击失败后
                if self.appear_then_click(self.I_FALSE, threshold=0.6):
                    continue
                if not self.appear(self.I_FALSE, threshold=0.6):
                    return False
        # 最后保证能点击 获得奖励
        if not self.is_skill and not self.wait_until_appear(self.I_REWARD, wait_time=2):
            # 有些的战斗没有下面的奖励，所以直接返回
            logger.info("There is no reward, Exit battle")
            return win
        else:
            if self.wait_until_appear(self.I_BCMJ_SKILL_ADD_CONFIRM, wait_time=2):
                while 1:
                    self.screenshot()
                    if self.appear_then_click(self.I_BCMJ_SKILL_ADD1, interval=1):
                        break
                    if self.appear_then_click(self.I_BCMJ_SKILL_ADD2, interval=1):
                        break
                    if self.appear_then_click(self.I_BCMJ_BLESS, interval=1):
                        break
                    if self.appear_then_click(
                        self.I_BCMJ_PROPERTY_ADD_CRITICAL, interval=1
                    ):
                        break
                    if self.appear_then_click(
                        self.I_BCMJ__DEFALUT_ATTRIBUTE, interval=1
                    ):
                        break
                if self.appear_then_click(self.I_BCMJ_SKILL_ADD_CONFIRM, interval=1):
                    return win

        logger.info("Get reward")
        while 1:
            self.screenshot()
            # 如果出现领奖励
            # self.C_REWARD_2 在掉落物品过多的时候可能会点击到物品，导致脚本卡死
            action_click = random.choice(
                [self.C_REWARD_1, self.C_REWARD_3]
            )
            if self.appear_then_click(
                self.I_REWARD, action=action_click, interval=1.5
            ) or self.appear_then_click(
                self.I_REWARD_GOLD, action=action_click, interval=1.5
            ):
                continue
            if self.appear(self.O_FIRE, interval=2):
                break

        return win

    def switch_hero(self, layer: Layer):
        """切换英杰"""
        self.ui_goto_page(pages.page_hero_test)
        switch_hero_dict: dict = {
            Layer.YANWU: (self.I_CHECK_HERO1, self.I_SWITCH_HERO1),  # 源赖光
            Layer.MIJING: (self.I_CHECK_HERO1, self.I_SWITCH_HERO1),  # 源赖光
            Layer.CHUANCHENG: (self.I_CHECK_HERO2, self.I_SWITCH_HERO2),  # 藤原道长
            Layer.MENGXU: (self.I_CHECK_HERO2, self.I_SWITCH_HERO2),  # 藤原道长
        }
        check_hero_img, switch_hero_img = switch_hero_dict[layer]
        while True:
            self.screenshot()
            if self.appear_then_click(switch_hero_img, interval=1):
                continue
            appeared = self.appear(check_hero_img, interval=1)
            if not appeared and self.appear(self.I_CHECK_HERO_TEST):
                self.click(self.C_SWITCH_HERO_BTN, interval=1.5)
                continue
            if appeared:
                break

    def can_run(self, layer: Layer) -> bool:
        """检查是否可以运行
        :return: True(default): can run, False: cannot run
        """
        check_func: dict[Layer, Callable] = {
            Layer.MIJING: self.check_art_war_card,
            Layer.CHUANCHENG: self.check_level_max,
        }
        if check_func.get(layer, None) is not None:
            return check_func[layer]()
        return True

    def check_art_war_card(self) -> bool:
        """兵藏秘境 看看是否有兵道帖"""
        self.screenshot()
        cu = self.O_ART_WAR_CARD.ocr(image=self.device.image)
        if cu[0] >= 1:
            logger.info("Art war card is enough")
            return True
        cu = self.O_ART_WAR_CARD_PLUS.ocr(image=self.device.image)
        # 转换为int
        if cu != "":
            cu = int(cu)
        else:
            cu = 0
        if cu >= 1:
            logger.info("Art war card is not enough, but plus card is enough")
            return True
        logger.warning("Art war card is not enough")
        return False

    def check_level_max(self):
        """检查御灵等级是否已经满级"""
        self.screenshot()
        if self.appear(self.I_HERO_EXP_MAX):
            logger.info('Experience is already maxed out, exit battle')
            return False
        return True

    def check_and_switch_soul(self):
        """检查并切换御魂"""
        if self.conf.switch_soul_config.enable:
            self.ui_goto_page(pages.page_shikigami_records)
            self.run_switch_soul(self.conf.switch_soul_config.switch_group_team)
        if self.conf.switch_soul_config.enable_switch_by_name:
            self.ui_goto_page(pages.page_shikigami_records)
            self.run_switch_soul_by_name(self.conf.switch_soul_config.group_name, self.conf.switch_soul_config.team_name)

    def open_exp_buff(self):
        """启用经验加成"""
        exp_50_buff_enable = self.conf.herotest.exp_50_buff_enable_help
        exp_100_buff_enable = self.conf.herotest.exp_100_buff_enable_help
        if exp_50_buff_enable or exp_100_buff_enable:
            self.ui_goto_page(pages.page_main)
            self.open_buff()
            self.exp_100(exp_100_buff_enable)
            self.exp_50(exp_50_buff_enable)
            self.close_buff()

    def close_exp_buff(self):
        """关闭经验加成"""
        exp_50_buff_enable = self.conf.herotest.exp_50_buff_enable_help
        exp_100_buff_enable = self.conf.herotest.exp_100_buff_enable_help
        if exp_50_buff_enable or exp_100_buff_enable:
            self.ui_goto_page(pages.page_main)
            self.open_buff()
            self.exp_100(False)
            self.exp_50(False)
            self.close_buff()

    def check_and_lock_team(self):
        """检查并锁定阵容"""
        if self.conf.general_battle.lock_team_enable:
            logger.info("Lock team")
            self.ui_click(self.I_UNLOCK, self.I_LOCK, interval=0.8)
        else:
            logger.info("Unlock team")
            self.ui_click(self.I_LOCK, self.I_UNLOCK, interval=0.8)

    def init_pages(self):
        """初始化页面"""
        match self.conf.herotest.layer:
            case Layer.YANWU:
                self.page_hero_mode = pages.Page(self.I_CHECK_HERO1_EXP)
                pages.page_hero_test.link(button=self.I_GBB, destination=self.page_hero_mode)
            case Layer.MIJING:
                self.page_hero_mode = pages.Page(self.I_CHECK_HERO1_SKILL)
                pages.page_hero_test.link(button=self.I_BCMJ, destination=self.page_hero_mode)
                self.is_skill = True
            case Layer.CHUANCHENG:
                self.page_hero_mode = pages.Page(self.I_CHECK_HERO2_EXP)
                pages.page_hero_test.link(button=self.I_ENTER_CCSL, destination=self.page_hero_mode)
            case Layer.MENGXU:
                self.page_hero_mode = pages.Page(self.I_CHECK_HERO2_SKILL)
                pages.page_hero_test.link(button=self.I_ENTER_MXMJ, destination=self.page_hero_mode)
                self.is_skill = True
            case _:
                raise ValueError(f'Unknown Layer {Layer}')
        self.page_hero_mode.link(button=self.I_BACK_YOLLOW, destination=pages.page_hero_test)


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    c = Config("oas1")
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
