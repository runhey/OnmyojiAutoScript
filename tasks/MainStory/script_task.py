# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from module.logger import logger
import random
from time import sleep

from module.exception import TaskEnd
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from tasks.MainStory.assets import MainStoryAssets
from tasks.Restart.assets import RestartAssets


class ScriptTask(GeneralBattle, GameUi, MainStoryAssets):

    def run(self):
        self.do_run()

    def do_run(self):
        self.ui_get_current_page()
        self.ui_goto(page_main)
        self.I_THREE_POINTS.method = 'Binarize matching'
        self.I_THREE_POINTS_2.method = 'Binarize matching'
        self.I_QUESTION_DIALOGUE.method = 'Binarize matching'

        while 1:
            # 庭院进入剧情
            story_ing = False
            while 1:
                self.screenshot()
                # 关闭获取新式神、阴阳师界面
                if self.appear_then_click(RestartAssets.I_LOGIN_RED_CLOSE, interval=1):
                    continue
                if story_ing or self.appear(self.I_THREE_POINTS, interval=1):
                    story_ing = True
                    # 退出放第一个：不然可能进入剧情后一直识别I_THREE_POINTS
                    if story_ing and self.appear(self.I_BACK, interval=1):
                        break
                    if self.appear_then_click(self.I_THREE_POINTS, interval=1):
                        continue
                    if self.appear_then_click(self.I_SKIP_DIALOGUE, interval=1):
                        continue
                    continue
                elif not story_ing:
                    break

            if not story_ing:
                break

            appear_failed = 0
            # 点击一系列对话
            while 1:
                self.screenshot()
                if (self.appear_then_click(self.I_THREE_POINTS_2, interval=1)
                        or self.appear_then_click(self.I_QUESTION_DIALOGUE, interval=1)
                        or self.appear_then_click(self.I_SKIP_DIALOGUE, interval=1)
                        or self.appear_then_click(self.I_EYE, interval=1)
                        or self.appear_then_click(RestartAssets.I_LOGIN_RED_CLOSE, interval=1)
                        or self.appear_then_click(self.I_VIDEO_CLOSE, interval=1)):
                    continue
                appear_failed += 1
                if appear_failed > 8:
                    self.switch_bin_threshold()
                    appear_failed = 0
                    continue
                if self.appear_then_click(self.I_RES_BATTLE_IN, interval=1):
                    # 执行了start battle，但其实没有进入战斗???
                    self.ui_click_until_smt_disappear(self.I_RES_BATTLE_IN, stop=self.I_RES_BATTLE_IN, interval=1)
                    self.start_battle()
                    continue
                elif self.appear_then_click(self.I_SPEED_1_X, interval=1):
                    self.wait_until_disappear(self.I_SPEED_2_X)
                    continue
                elif self.is_in_battle(True):
                    # 随机左右点击点到了战斗
                    self.start_battle()
                    continue
                elif self.appear(self.I_GET_SHIKIAGMI, interval=1):
                    # 获取新式神
                    self.ui_click_until_smt_disappear(self.C_LEFT_CLICK, stop=self.I_GET_SHIKIAGMI, interval=1)
                    continue
                elif self.appear(self.I_MASK_BACK, interval=1):
                    # 返回按钮如果有遮罩层：获取新物品
                    self.ui_click_until_smt_disappear(self.C_LEFT_CLICK, stop=self.I_MASK_BACK, interval=1)
                    continue
                elif self.appear(self.I_CHECK_MAIN, interval=1) or self.appear(self.I_MAIN_GOTO_EXPLORATION, interval=1):
                    break
                else:
                    # 匹配不到，可能被遮挡，滑动一下
                    if random.randint(0, 1) % 2 == 1:
                        self.click(self.C_LEFT_CLICK, interval=5)
                    else:
                        self.click(self.C_RIGHT_CLICK, interval=5)
                    sleep(2)

        self.ui_get_current_page()
        self.ui_goto(page_main)
        self.set_next_run(task='MainStory', success=True, finish=True)
        raise TaskEnd

    def start_battle(self):
        self.run_general_battle()

    def switch_bin_threshold(self):
        pre_value = self.I_THREE_POINTS_2.bin_threshold
        bin_threshold = [45, 100, 200]
        pre_value = next((value for value in bin_threshold if value > pre_value), bin_threshold[0])

        logger.info(f"Switch bin threshold to {pre_value}")
        self.I_THREE_POINTS_2.bin_threshold = pre_value
        self.I_QUESTION_DIALOGUE.bin_threshold = pre_value

if __name__ == "__main__":
    from tasks.MainStory.assets import MainStoryAssets
    from module.base.utils import save_image
    from module.device.device import Device
    from module.config.config import Config
    from tasks.Restart.assets import RestartAssets

    config = Config('oas1')
    device = Device(config)
    t = ScriptTask(config, device)
    device.screenshot()

    # save_image(device.image, "./tasks/MainStory/res/1.png")

    # points__ = MainStoryAssets.I_THREE_POINTS_2
    points__ = MainStoryAssets.I_QUESTION_DIALOGUE
    points__.method = 'Binarize matching'
    points__.bin_threshold = 100
    matching = points__.test_match(device.image)
    print(matching)

    # print(RestartAssets.I_LOGIN_RED_CLOSE())


    # points__ = MainStoryAssets.I_RES_BATTLE_IN
    # matching = points__.test_match(device.image)
    # print(matching)
