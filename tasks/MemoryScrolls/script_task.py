# This Python file uses the following encoding: utf-8
# @author ghg11
# github https://github.com/ghg11
from time import sleep
from enum import Enum
from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_summon
from tasks.MemoryScrolls.assets import MemoryScrollsAssets
from tasks.MemoryScrolls.config import ScrollNumber


class ScriptTask(GameUi, MemoryScrollsAssets):

    # 进入绘卷主界面
    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_summon)

        # 循环寻找&点击绘卷入口
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_MS_ENTER, interval=1):
                continue
            if self.appear(self.I_MS_MAIN):
                break

                sleep(3)
            # (根据config进入指定分卷,不会写所以暂定卷一)
            if self.appear_then_click(self.I_MS_MAIN, self.C_MS_SCROLL_1, interval=3):
                continue
            # 检测到100% 任务完成 退出循环
            if self.appear(self.I_MS_COMPLETE):
                logger.info('Scroll already completed')
                break


        # 捐献小碎片直至不足
        while 1:
             self.screenshot()
             if self.appear(self.I_MS_ZERO_S):
                 break
             if self.appear(self.I_MS_CONTRIBUTE):
                 self.swipe(self.S_MS_SWIPE_S,interval=1)
                 continue
             if self.appear_then_click(self.I_MS_CONTRIBUTE, interval=1):
                 continue
             if self.appear_then_click(self.I_MS_CONTRIBUTED,self.C_MS_CONTRIBUTED,interval=3):
                 continue
             continue



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()





