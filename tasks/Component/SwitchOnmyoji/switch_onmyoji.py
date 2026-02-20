from module.atom.image import RuleImage
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
        hero = [Onmyoji.YORIMITSU, Onmyoji.MICHINAGA]
        if onmyoji in hero:
            self.ui_click(self.I_ONMYOJI_CHECK, self.I_HERO_CHECK, interval=0.8)
            self.switch_role(onmyoji, self._get_hero_battle_dict(), self.I_HERO_CHECK)
        else:
            self.ui_click(self.I_HERO_CHECK, self.I_ONMYOJI_CHECK, interval=0.8)
            self.switch_role(onmyoji, self._get_onmyoji_battle_dict(), self.I_ONMYOJI_CHECK)
        logger.info(f'Switch onmyoji: {onmyoji.name}[{onmyoji.value}]')

    def switch_role(self, role: Onmyoji, battle_dict: dict, check_img: RuleImage):
        """
        通用切换角色方法
        :param role: 角色类型 (阴阳师或英杰)
        :param battle_dict: 角色与战斗图标的映射
        :param check_img: 检查是否回到主界面的图标
        """
        while True:
            self.screenshot()
            if any(self.appear(battle_icon) for battle_icon in battle_dict.values()):
                break
            self.appear_then_click(self.I_ONMYOJI_SWITCH, interval=0.8)
        battle_img = battle_dict.get(role, None)
        if not battle_img:
            raise ValueError('Incorrect role type')
        while True:
            self.screenshot()
            if self.appear(check_img, interval=0.8):
                break
            if self.appear(battle_img, interval=0.8):
                self.ui_click(self.I_UI_BACK_BLUE, check_img, interval=1.2)
                break
            self.click(battle_img, interval=1.2)

    def _get_onmyoji_battle_dict(self):
        """获取阴阳师出战图标映射"""
        return {
            Onmyoji.SEIMI: self.I_SEIMI_BATTLE,
            Onmyoji.KAGURA: self.I_KAGURA_BATTLE,
            Onmyoji.HIROMASA: self.I_HIROMASA_BATTLE,
            Onmyoji.YAO_BIKUNI: self.I_YAO_BIKUNI_BATTLE,
        }

    def _get_hero_battle_dict(self):
        """获取英杰出战图标映射"""
        return {
            Onmyoji.YORIMITSU: self.I_YORIMITSU_BATTLE,
            Onmyoji.MICHINAGA: self.I_MICHINAGA_BATTLE,
        }


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = SwitchOnmyoji(c, d)

    t.switch_onmyoji(Onmyoji.MICHINAGA)
