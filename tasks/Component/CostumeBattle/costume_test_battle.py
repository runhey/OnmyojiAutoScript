# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.page import page_kekkai_toppa
from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType, GeneralBattleConfig
from tasks.RyouToppa.script_task import ScriptTask as ScriptTaskBase
from tasks.Component.Costume.config import BattleType

# 突破/前提是有突破券
class ScriptTask(ScriptTaskBase):

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_kekkai_toppa)

        self.attack()

        # self.fire(1)
        # self.run_general_battle_back(con.general_battle_config)
        # self.fire(1)
        # self.run_general_battle_back(con.general_battle_config)

    @property
    def battle_config(self) -> GeneralBattleConfig:
        _con = GeneralBattleConfig()
        # 绿标测试
        _con.green_enable = True
        _con.green_mark = GreenMarkType.GREEN_LEFT4
        return _con

    def attack(self):
        import time
        from tasks.RyouToppa.script_task import area_map
        from tasks.RealmRaid.assets import RealmRaidAssets

        index = 1
        if not self.check_area(index):
            return False

        rcl = area_map[index].get("rule_click")
        click_failure_count = 0
        while True:
            self.screenshot()
            if click_failure_count >= 3:
                logger.warning("Click failure, check your click position")
                return False
            if not self.appear(self.I_TOPPA_RECORD, threshold=0.85):
                time.sleep(1)
                self.screenshot()
                if self.appear(self.I_TOPPA_RECORD, threshold=0.85):
                    continue
                logger.info("Start attach area [%s]" % str(index + 1))
                return self.run_general_battle_back(config=self.battle_config)

            if self.appear_then_click(RealmRaidAssets.I_FIRE, interval=2, threshold=0.8):
                click_failure_count += 1
                continue
            if self.click(rcl, interval=5):
                continue

    def set_costume(self, costume: BattleType=BattleType.COSTUME_BATTLE_DEFAULT):
        self.config.model.global_game.costume_config.costume_battle_type = costume
        self.check_costume()
        logger.info('Set costume to %s' % self.config.model.global_game.costume_config.costume_battle_type)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.set_costume(BattleType.COSTUME_BATTLE_1)
    t.run()
