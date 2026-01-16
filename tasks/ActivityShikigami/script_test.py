
import datetime
from abc import ABC

from module.config.config import Config
from module.device.device import Device

from tasks.ActivityShikigami.page import page_climb_act
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.script_task import ScriptTask


class ImplScriptTask(ScriptTask, ABC):
    def test_battle_main(self) -> bool:
        # 从别的地方到活动主页面
        self.ui_get_current_page()
        self.ui_goto(page_climb_act)
        # 从活动主页面到默认战斗页面
        self.ui_click(self.I_TO_BATTLE_MAIN, stop=self.I_CHECK_BATTLE_MAIN, interval=1)
        # 从默认战斗页面到式神录 再返回
        self.ui_click(self.I_BATTLE_MAIN_TO_RECORDS, stop=self.I_CHECK_RECORDS, interval=1)
        self.ui_click(self.I_UI_BACK_YELLOW, stop=self.I_CHECK_BATTLE_MAIN, interval=1)
        self.ui_click(self.I_UI_BACK_YELLOW, stop=self.I_TO_BATTLE_MAIN, interval=1)
        return True


class ScriptTest:
    def __init__(self, config: str = 'oas1'):
        self.config = Config(config)
        self.device = Device(self.config)
        self.task = ImplScriptTask(self.config, self.device)


if __name__ == '__main__':
    test = ScriptTest(config='oas1')
    assert test.task.test_battle_main()


























