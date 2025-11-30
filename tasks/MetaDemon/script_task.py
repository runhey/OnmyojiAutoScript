# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from cached_property import cached_property
from datetime import datetime
from time import sleep


from module.base.timer import Timer
from module.logger import logger
from module.exception import TaskEnd


from tasks.Component.RightActivity.right_activity import RightActivity
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.MetaDemon.config import MetaDemon, DefaultStrategy, Strategy
from tasks.MetaDemon.assets import MetaDemonAssets
from tasks.Restart.assets import RestartAssets
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets



class Star56(GameUi, MetaDemonAssets):

    @cached_property
    def cached_strategies(self) -> dict[str, list[int]]:
        return Strategy.parse_all(self.config.meta_demon.md_strategies)

    @cached_property
    def cached_default_group_team(self) -> list[int]:
        return Strategy.parse_group_team(self.config.meta_demon.md_default_strategy.md_preset_group_team_default_1) \
            + Strategy.parse_group_team(self.config.meta_demon.md_default_strategy.md_preset_group_team_default_2)

    def is_star56(self):
        if not self.appear(self.I_STAR56_POS_1):
            return True
        return False

    def hp_threshold_low(self, image):
        """
        @param image:
        @return: 血量小于阈值返回True
        """
        return self.appear(self.I_STAR56_HP_THRESHOLD_F) and not self.appear(self.I_STAR56_HP_THRESHOLD_T)

    @classmethod
    def strategy2group_team(cls, strategies: dict[str, list[int]], detect_name: str) -> list[int] | None:
        """
        先是默认的完全匹配，然后是1个字符不同，最后是2个字符不同
        @param strategies:
        @param detect_name:
        @return:
        """
        for i in range(2):
            for key_name in strategies:
                if len(key_name) != len(detect_name):
                    continue
                diff_count = sum(1 for c1, c2 in zip(key_name, detect_name) if c1 != c2)
                if diff_count <= i < len(detect_name):
                    return strategies[key_name]
        return None

    def get_group_team(self, detect_name: str) -> list[int]:
        tmp = self.strategy2group_team(self.cached_strategies, detect_name)
        return tmp if tmp else self.cached_default_group_team


class ScriptTask(RightActivity, GeneralBattle, SwitchSoul, Star56):

    def run(self):
        if self.config.meta_demon.switch_soul.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(self.config.meta_demon.switch_soul.switch_group_team)

        if self.config.meta_demon.switch_soul.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(self.config.meta_demon.switch_soul.group_name,
                                         self.config.meta_demon.switch_soul.team_name)

        self.enter(self.I_RIGHT_ENTER)
        while 1:
            self.screenshot()
            if self.appear(self.I_FIND_DEMON) or self.appear(self.I_BATTLE_DEMON):
                break

            if self.ui_reward_appear_click():
                continue
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1.5):
                continue
            if self.appear_then_click(self.I_ENTER_ENSURE, interval=1):
                continue
            if self.appear_then_click(self.I_ENTER2, interval=1):
                continue
        if self.config.meta_demon.meta_demon_config.meta_crafting_card:
            self.crafting()

        boss_timer = Timer(50)
        boss_timer.start()
        first_battle_for_easy_boss = True
        while 1:
            battle_processing = False
            is_hard_boss = False  # 五星或者六星
            self.screenshot()
            if not (self.appear(self.I_FIND_DEMON) or self.appear(self.I_BATTLE_DEMON)):
                continue

            # 先看自己有没有鬼王要打
            if not self.appear(self.I_BOSS_EMPTY) and self.appear(self.I_BOSS_CONVENE):
                logger.info('Try to battle boss from self')
                self.click(self.I_BOSS_EMPTY, interval=1.5)
                battle_processing = True
                if self.is_star56():
                    is_hard_boss = True
            # 看别人的是否给我共享鬼王
            if not battle_processing:
                if not self.appear(self.I_BOSS_EMPTY_1) and self.ocr_appear(self.O_BOSS_EMPTY_1):
                    logger.info('Try to battle boss 1 from others')
                    self.click(self.I_BOSS_EMPTY_1, interval=1.5)
                    self.ui_click(self.I_BOSS_EMPTY_1, stop=self.I_BATTLE_DEMON, interval=1.5)
                    battle_processing = True
                    is_hard_boss = True
                elif not self.appear(self.I_BOSS_EMPTY_2):
                    logger.info('Try to battle boss 2 from others')
                    self.click(self.I_BOSS_EMPTY_2, interval=1.5)
                    self.ui_click(self.I_BOSS_EMPTY_1, stop=self.I_BATTLE_DEMON, interval=1.5)
                    battle_processing = True
                    is_hard_boss = True
            # 是否喝茶 疲劳满了就不打了
            current_exhaustion = self.current_exhaustion()
            if current_exhaustion > 100:
                if self.config.meta_demon.meta_demon_config.auto_tea:
                    logger.info('Exhaustion is full, buy tea')
                    boss_timer.reset()
                    self.buy_tea()
                else:
                    logger.info('Exhaustion is full, exit')
                    break
            # 超时结束
            if boss_timer.reached():
                logger.info('Time out, exit')
                break
            # 5/6星特殊处理 + 使用自定义策略组
            target_group_team = [None, None]
            if is_hard_boss:
                logger.info('Hard boss')
                if self.config.meta_demon.meta_demon_config.md_use_strategy:
                    detect_full_name = self.O_MD_FULL_NAME.ocr_single(self.device.image)
                    logger.info(f'detect_full_name: {detect_full_name}')
                    if not detect_full_name:
                        detect_full_name = ''
                    group_team = self.get_group_team(detect_full_name)
                    if self.hp_threshold_low(self.device.image):
                        logger.info('Hp threshold low')
                        target_group_team = group_team[2:4]
                    else:
                        logger.info('Hp threshold high')
                        target_group_team = group_team[0:2]
            else:
                if self.config.meta_demon.meta_demon_config.md_use_strategy and first_battle_for_easy_boss:
                    logger.info('Normal boss first battle use default group team')
                    target_group_team = self.cached_default_group_team
            if battle_processing and self.appear(self.I_BATTLE_DEMON):
                logger.info(f'preset group team: {target_group_team}')
                self.battle_boss(target_group_team[0], target_group_team[1])
                if first_battle_for_easy_boss:
                    first_battle_for_easy_boss = False
                if is_hard_boss:
                    first_battle_for_easy_boss = True
                boss_timer.reset()
                continue

            # 自己召唤鬼王
            if current_exhaustion < 90 and self.find_demon():
                boss_timer.reset()
                continue

        # 退出
        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_MAIN, interval=1.4)
        logger.info('Exit MetaDemon')
        self.set_next_run(task="MetaDemon", success=True)
        raise TaskEnd

    def current_exhaustion(self) -> int:
        self.screenshot()
        cu, res, total = self.O_MD_EXHAUSTION.ocr(self.device.image)
        return int(cu)

    def buy_tea(self):
        pass

    def crafting(self):
        """
        把一星合成二星
        @return:
        """
        logger.info('Star crafting 1 star to 2 star')
        self.ui_click(self.I_CRAFTING_1, self.I_CRAFTING_START, interval=1.5)
        timer = Timer(3).start()
        count = 0
        while 1:
            self.screenshot()
            if self.ui_reward_appear_click():
                timer.reset()
                continue
            if timer.reached() or count > 3:
                break
            if not self.ocr_appear(self.O_CRAFTING_CARD_1):
                break
            if self.appear(self.I_CRAFTING_EMPTY) or self.appear(self.I_CRAFTING_EMPTY_NEW):
                if self.appear_then_click(self.I_CRAFTING_CARD_STAR_1, interval=1):
                    continue
            else:
                self.appear_then_click(self.I_CRAFTING_START, interval=3)
                count += 1
                timer.reset()
                continue
        logger.info('Finish star crafting')
        self.ui_click_until_disappear(self.I_UI_BACK_RED, interval=1)
        sleep(0.5)

    def find_demon(self) -> bool:
        """
        召唤鬼王
        @return:
        """
        logger.info('Find demon')
        while 1:
            self.screenshot()
            if self.appear(self.I_BATTLE_DEMON) and not self.appear(self.I_BOSS_EMPTY):
                break
            if self.appear_then_click(self.I_FIND_DEMON, interval=3.5):
                continue
        self.screenshot()
        if self.is_star56():
            logger.info('Star 5 or 6 demon found')
            while 1:
                sleep(0.4)
                self.screenshot()
                detect_full_name = self.O_MD_FULL_NAME.ocr_single(self.device.image)
                if detect_full_name:
                    break
            logger.info(f'召唤到高星鬼王: {detect_full_name}')
            self.config.notifier.push(content=f'召唤到高星鬼王: {detect_full_name}', title='超鬼王')
        return True

    def battle_boss(self, group: int = None, team: int = None) -> bool:
        logger.info('Battle boss')
        self.ui_click_until_disappear(self.I_BATTLE_DEMON, interval=1.8)
        battle_config = GeneralBattleConfig()
        battle_config.lock_team_enable = False
        if group is None and team is None:
            battle_config.preset_enable = False
            success = self.run_general_battle(battle_config)
            return True if success else False
        # 针对5/6星的挑战
        else:
            battle_config.preset_enable = True
            battle_config.preset_group = group
            battle_config.preset_team = team
            tmp_battle_count = self.current_count
            self.current_count = 0
            success = self.run_general_battle(battle_config)
            self.current_count = tmp_battle_count + 1
            return True if success else False

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 重写
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info("Start battle process")
        self.boss_mark_reset()
        while 1:
            self.screenshot()
            # if self.appear_then_click(self.I_WIN, interval=1):
            #     continue
            if self.appear(self.I_WIN):
                logger.info('Win battle')
                self.ui_click_until_disappear(self.I_WIN)
                return True

            if self.appear(self.I_MD_BATTLE_FAILURE):
                logger.warning('False battle')
                self.ui_click_until_disappear(self.I_MD_BATTLE_FAILURE)
                return False
            if self.boss_mark():
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()

