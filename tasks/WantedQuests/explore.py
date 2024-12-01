from cached_property import cached_property

from module.atom.animate import RuleAnimate
from module.atom.image import RuleImage
from module.base.timer import Timer
from module.logger import logger
from tasks.Exploration.base import BaseExploration, Scene
from tasks.Exploration.version import HighLight


class ExploreWantedBoss(Exception):
    # 出现一种情况，要求的怪是仅仅最后的Boss，其他小怪不是
    pass


class WQExplore(BaseExploration, HighLight):
    _cnt_exploration: int = 0

    @cached_property
    def _match_end(self):
        return RuleAnimate(self.I_SWIPE_END)

    def explore(self, goto: RuleImage, num: int):
        logger.info(f'Start exploring with number: {num}')
        explore_init = False
        explore_only_boss: bool = True
        _cnt_exploration = 0
        search_fail_cnt = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_UI_BACK_RED) and self.appear(self.I_E_EXPLORATION_CLICK):
                break
            if self.appear_then_click(goto, interval=2):
                continue

        while 1:
            scene = self.get_current_scene(reuse_screenshot=False)
            # 进入探索
            if scene == Scene.ENTRANCE:
                if _cnt_exploration >= num:
                    logger.info('Execution exploration end')
                    self.ui_click_until_disappear(self.I_UI_BACK_RED)
                    if explore_only_boss:
                        raise ExploreWantedBoss
                    break
                self.ui_click(self.I_E_EXPLORATION_CLICK, stop=self.I_E_SETTINGS_BUTTON)
                continue
            # 探索大世界
            elif scene == Scene.WORLD:
                self.wait_until_stable(
                    self.I_CHECK_EXPLORATION,
                    timer=Timer(limit=0.5, count=2),
                    timeout=Timer(2, count=10)
                )
                curr_scene = self.get_current_scene(reuse_screenshot=False)
                if curr_scene == Scene.WORLD and _cnt_exploration >= num:
                    logger.info('All Done')
                    break
                continue
            # 探索里面
            elif scene == Scene.MAIN:
                if not explore_init:
                    count=0
                    while count<5:
                        if self.appear(self.I_E_AUTO_ROTATE_ON):
                            break
                        if self.appear(self.I_E_AUTO_ROTATE_OFF, interval=1.5):
                            self.click(self.I_E_AUTO_ROTATE_OFF)
                            count+=1
                    explore_init = True
                    continue
                # 小纸人
                if self.appear(self.I_BATTLE_REWARD):
                    if self.ui_get_reward(self.I_BATTLE_REWARD):
                        continue
                # boss
                if self.appear(self.I_BOSS_BATTLE_BUTTON):
                    if self.fire(self.I_BOSS_BATTLE_BUTTON):
                        logger.info(f'Boss battle, minions cnt {self.minions_cnt}')
                        _cnt_exploration += 1
                        explore_only_boss = False
                    continue
                # 小怪
                if self.appear(self.TEMPLATE_GIF) and self.fire(self.TEMPLATE_GIF):
                    explore_only_boss = False
                    logger.info(f'Fight, minions cnt {self.minions_cnt}')
                # 向后拉,寻找怪
                if search_fail_cnt >= 4:
                    search_fail_cnt = 0
                    if self._match_end.stable(self.device.image):
                        _cnt_exploration += 1
                        self.quit_explore()
                        continue
                    if self.swipe(self.S_SWIPE_BACKGROUND_RIGHT, interval=3):
                        continue
                else:
                    search_fail_cnt += 1
            elif scene == Scene.UNKNOWN:
                continue


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from tasks.WantedQuests.assets import WantedQuestsAssets

    config = Config('oas1')
    device = Device(config)
    t = WQExplore(config, device)
    t.explore(goto=WantedQuestsAssets.I_GOTO_1, num=2)
