import random

from module.logger import logger
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr

from tasks.Component.GeneralBattle.battle_wait import (
    BattleWait, battle_wait_strategy, battle_wait_options,
    OptionPrepareDefault, OptionPresetDefault, OptionGreenDefault, OptionRandomclickDefault,
    runtime,
)
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig, GreenMarkType


class Battle(BattleWait):

    def start_fire(self, buttons: list[RuleOcr | RuleImage], checks: list[RuleImage]) -> bool:
        """
        感觉这种适配要很难
        Args:
            buttons: 出现就点击
            checks: 必须在当前界面

        Returns:
            在战斗中就返回
        """
        click_times, max_times = 0, random.randint(4, 8)
        while 1:
            self.screenshot()
            if self.is_in_battle(False):
                break
            if click_times >= max_times:
                logger.warning(f'Climb {self.climb_type} cannot enter, maybe already end, try next')
                return False
            if (self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1) or
                    self.appear_then_click(self.I_UI_CONFIRM, interval=1)):
                continue
            if any([self.appear(check, interval=1) for check in checks]):
                for button in buttons:
                    if isinstance(button, RuleOcr) and self.ocr_appear_click(button, interval=2):
                        click_times += 1
                        logger.info(f'Try click fire, remain times[{max_times - click_times}]')
                        continue
                    if isinstance(button, RuleImage) and self.appear_then_click(button, interval=2):
                        click_times += 1
                        logger.info(f'Try click fire, remain times[{max_times - click_times}]')
                        continue
        return True

    @battle_wait_strategy()
    def battle_wait(self, *args, **kwargs):
        return self.battle_wait_with_strategy(*args, **kwargs)


    def battle_run(self):
        with battle_wait_strategy(), battle_wait_options():
            return self.battle_wait()

    @classmethod
    def battle_count_reached(cls, limit: int) -> bool:
        """
        判断当前任务累计战斗次数是否已达到上限。
        对比的是新流程的任务级计数 per_task.count（每完成一场结算 +1）。

        Args:
            limit: 上限对比值，如 FallenSun 的 limit_count。

        Returns:
            达到或超过上限返回 True，否则 False。
        """
        count = runtime.pub_ctx.per_task.count if runtime.pub_ctx else 0
        return count >= limit

    @classmethod
    def battle_state_reset(cls):
        runtime.reset_per_task()
        runtime.reset_per_battle()

    def battle_setup(self):
        pass

    def loadout_from_config(self, conf: GeneralBattleConfig) -> tuple[dict, dict]:
        """
        与 loadout_default 相同格式，但由 GeneralBattleConfig 驱动：。
        """
        strategies, options = self.loadout_default()
        options['prepare'] = OptionPrepareDefault(lock_team=conf.lock_team_enable)
        if conf.preset_enable:
            options['preset'] = OptionPresetDefault(
                preset_enable=True, preset_group=conf.preset_group, preset_team=conf.preset_team,
            )
        if conf.green_enable:
            options['green'] = OptionGreenDefault(green_enable=True, green_mark=conf.green_mark)
        if conf.random_click_swipt_enable:
            strategies['randomclick'] = 'default'
            options['randomclick'] = OptionRandomclickDefault()
        return strategies, options


from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
class BattleTest(Battle, GeneralBattle, ActivityShikigamiAssets):

    def my_test_activity_prepare(self):
        """
        活动里面测试，需要先点击战斗准备阶段
        """
        strategies, options = self.loadout_default()
        strategies['prepare'] = 'default'
        strategies['success'] = 'activity'
        options['prepare'] = OptionPrepareDefault(lock_team=False)
        self.loadout_show((strategies, options))
        with battle_wait_strategy(**strategies), battle_wait_options(**options):
            self.battle_wait()
            self.state_show()

    def my_test_activity_preset(self, preset_group: int = 5, preset_team: int = 3):
        """
        活动里面测试，准备阶段开启切阵容（预设）
        """
        strategies, options = self.loadout_default()
        strategies['preset'] = 'default'
        strategies['success'] = 'activity'
        options['preset'] = OptionPresetDefault(preset_enable=True, preset_group=preset_group, preset_team=preset_team)
        self.loadout_show((strategies, options))
        with battle_wait_strategy(**strategies), battle_wait_options(**options):
            self.battle_wait()
            self.state_show()

    def my_test_activity_green(self, green_mark: GreenMarkType = GreenMarkType.GREEN_LEFT1):
        """
        活动里面测试，绿标标记
        """
        strategies, options = self.loadout_default()
        strategies['green'] = 'default'
        strategies['success'] = 'activity'
        options['green'] = OptionGreenDefault(green_enable=True, green_mark=green_mark)
        self.loadout_show((strategies, options))
        with battle_wait_strategy(**strategies), battle_wait_options(**options):
            self.battle_wait()
            self.state_show()

    def my_test_activity_randomclick(
            self,
            start_delay: tuple[float, float] = (5.0, 10.0),
            cooldown: tuple[float, float] = (15.0, 30.0),
            trigger_probability: float = 0.6,
            execution_limit: tuple[int, int] = (1, 2),
    ):
        """
        活动里面测试，随机点击
        """
        strategies, options = self.loadout_default()
        strategies['randomclick'] = 'default'
        strategies['success'] = 'activity'
        options['randomclick'] = OptionRandomclickDefault(
            start_delay=start_delay,
            cooldown=cooldown,
            trigger_probability=trigger_probability,
            execution_limit=execution_limit,
        )
        self.loadout_show((strategies, options))
        with battle_wait_strategy(**strategies), battle_wait_options(**options):
            self.battle_wait()
            self.state_show()

    def my_test_activity_continuous(self):
        """
        活动里面测试，连续执行
        """
        strategies, options = self.loadout_default()
        strategies['prepare'] = 'default'
        strategies['success'] = 'activity'
        options['prepare'] = OptionPrepareDefault(lock_team=False)
        self.loadout_show((strategies, options))
        for i in range(5):
            with battle_wait_strategy(**strategies), battle_wait_options(**options):
                self.start_fire(buttons=[self.O_FIRE], checks=[self.I_CHECK_BATTLE_MAIN, self.I_CHECK_BATTLE_BOSS])
                self.battle_wait()
                self.state_show()



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    from tasks.Component.GeneralBattle.general_battle import GeneralBattle
    c = Config('oas1')
    d = Device(c)
    t = BattleTest(c, d)

    # t.my_test_activity_prepare()
    # t.my_test_activity_preset()
    # t.my_test_activity_green()
    # t.my_test_activity_randomclick()
    t.my_test_activity_continuous()
