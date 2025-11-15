from tasks.Component.SwitchOnmyoji.assets import SwitchOnmyojiAssets
from tasks.Component.SwitchOnmyoji.config import Onmyoji
from tasks.base_task import BaseTask
from module.logger import logger


class SwitchOnmyoji(BaseTask, SwitchOnmyojiAssets):

    def switch_onmyoji(self, onmyoji: Onmyoji):
        """
        切换阴阳师, 要求已经进入阴阳术界面, 最后会留在阴阳术界面
        :param onmyoji: 阴阳师
        """
        logger.hr('Switch onmyoji', 2)
        hero = [Onmyoji.YORIMITSU]
        if onmyoji in hero:
            self._switch_hero(onmyoji)
        else:
            self._switch_onmyoji(onmyoji)
        logger.info(f'Switch onmyoji: {onmyoji.name}[{onmyoji.value}]')

    def _switch_onmyoji(self, onmyoji: Onmyoji):
        """切换阴阳师"""
        onmyoji_battle_dict = {
            Onmyoji.SEIMI: self.I_SEIMI_BATTLE,
            Onmyoji.KAGURA: self.I_KAGURA_BATTLE,
            Onmyoji.HIROMASA: self.I_HIROMASA_BATTLE,
            Onmyoji.YAO_BIKUNI: self.I_YAO_BIKUNI_BATTLE,
        }
        self.ui_click(self.I_HERO_CHECK, self.I_ONMYOJI_CHECK, interval=0.8)
        # 进入阴阳师替换页面
        while not (self.appear(self.I_SEIMI_BATTLE) or self.appear(self.I_KAGURA_BATTLE)
                   or self.appear(self.I_HIROMASA_BATTLE) or self.appear(self.I_YAO_BIKUNI_BATTLE)):
            self.appear_then_click(self.I_ONMYOJI_SWITCH, interval=0.8)
            self.screenshot()
        onmyoji_battle = onmyoji_battle_dict.get(onmyoji, None)
        if not onmyoji_battle:
            raise ValueError('Incorrect onmyoji type')
        while True:
            self.screenshot()
            # 回到阴阳术页面则退出
            if self.appear(self.I_ONMYOJI_CHECK, interval=0.8):
                break
            if self.appear(onmyoji_battle, interval=0.8):
                self.ui_click(self.I_UI_BACK_BLUE, self.I_ONMYOJI_CHECK, interval=1.2)
                break
            # 出战对应阴阳师
            self.click(onmyoji_battle, interval=1.2)

    def _switch_hero(self, onmyoji: Onmyoji):
        """切换英杰"""
        self.ui_click(self.I_ONMYOJI_CHECK, self.I_HERO_CHECK, interval=0.8)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas3')
    d = Device(c)
    t = SwitchOnmyoji(c, d)

    t.switch_onmyoji(Onmyoji.YORIMITSU)
