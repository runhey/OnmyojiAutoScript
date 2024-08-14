import time

from module.logger import logger

from cached_property import cached_property
from datetime import datetime, timedelta

from tasks.SixRealms.moon_sea.map import MoonSeaMap
from tasks.SixRealms.moon_sea.l101 import MoonSeaL101
from tasks.SixRealms.moon_sea.l102 import MoonSeaL102
from tasks.SixRealms.moon_sea.l103 import MoonSeaL103
from tasks.SixRealms.moon_sea.l104 import MoonSeaL104
from tasks.SixRealms.moon_sea.l105 import MoonSeaL105
from tasks.SixRealms.common import MoonSeaType


class MoonSea(MoonSeaMap, MoonSeaL101, MoonSeaL102, MoonSeaL103, MoonSeaL104, MoonSeaL105):

    @cached_property
    def island_func(self) -> dict:
        return {
            MoonSeaType.island101: self.run_l101(),
            MoonSeaType.island102: self.run_l102(),
            MoonSeaType.island103: self.run_103(),
            MoonSeaType.island104: self.run_l104(),
            MoonSeaType.island105: self.run_l105(),
        }

    @property
    def _conf(self):
        return self.config.model.six_realms.six_realms_gate

    def _run_moon_sea(self):
        # 在六道界面
        limit_time = self._conf.limit_time
        max_cont = self._conf.limit_count
        max_time: timedelta = timedelta(
            hours=limit_time.hour,
            minutes=limit_time.minute,
            seconds=limit_time.second
        )
        cnt = 0
        while 1:
            if cnt >= max_cont:
                logger.info('Run out of count, exit')
                break
            if datetime.now() - self.start_time >= max_time:
                logger.info('Run out of time, exit')
                break
            self.one()
            cnt += 1
        logger.info('Exit Moon Sea')


    def one(self):
        self.cnt_skill101 = 1
        self._start()
        while 1:
            self.screenshot()
            if not self.in_main():
                continue
            isl_type, isl_num, isl_roi = self.decide()
            if isl_num == 1 and isl_type != MoonSeaType.island106:
                # 如果前一个，召唤一次宁息
                if self.cnt_skill101 >= 5:
                    # 如果柔风满级就不召唤
                    pass
                elif self.appear(self.I_M_STORE):
                    # 如果没有三百块就不能召唤
                    logger.info('There have no money to active store at the last island')
                    pass
                else:
                    self.activate_store()
                    self.wait_animate_stable(self.C_MAIN_ANIMATE_KEEP, timeout=3)
                    isl_type, isl_num, isl_roi = self.decide()
                    # 文字检测不一定发现到宁息
                    if isl_type != MoonSeaType.island101:
                        logger.warning('OCR not found island101')
                        logger.warning('Try to entry the island in the right randomly order')
                        self.entry_island_random()

            # 如果是boss
            if isl_type == MoonSeaType.island106:
                self.boss_team_lock()
                if self.boss_battle():
                    break
                else:
                    continue

            self.enter_island(isl_type=isl_type, isl_roi=isl_roi)
            isl_type = self.island_name()
            match isl_type:
                case MoonSeaType.island101: self.run_l101()
                case MoonSeaType.island102: self.run_l102()
                case MoonSeaType.island103: self.run_103()
                case MoonSeaType.island104: self.run_l104()
                case MoonSeaType.island105: self.run_l105()
            self.wait_animate_stable(self.C_MAIN_ANIMATE_KEEP, timeout=3)
            continue

    def _continue(self):
        logger.warning('Moon Sea Continue')
        while 1:
            self.screenshot()
            if self.in_main():
                break
            if self.appear_then_click(self.I_MCONINUE, interval=1):
                continue

    def _start(self):
        logger.hr('Moon Sea', 1)
        while 1:
            self.screenshot()
            if self.appear(self.I_MSTART):
                break
            if self.appear_then_click(self.I_MENTER, interval=1):
                continue
            if self.appear(self.I_MCONINUE):
                # 继续上一把的
                self._continue()
                return
        logger.info("Ensure select ShouZu")
        while 1:
            self.screenshot()
            if self.appear(self.I_MSHOUZU):
                break
            if self.appear_then_click(self.I_MSHUTEN, interval=3):
                continue
            if self.appear_then_click(self.I_MSHOUZU_SELECT, interval=1):
                continue
        logger.info("Ensure selected ShouZu")
        while 1:
            self.screenshot()
            if self.appear(self.I_PREPARE_BATTLE):
                break
            if self.appear_then_click(self.I_MSTART_UNCHECK, interval=0.6):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                continue
            if self.appear_then_click(self.I_MSKIP, interval=1.5):
                continue
            if self.appear_then_click(self.I_MSTART, interval=3):
                continue
            if self.appear_then_click(self.I_MSTART_CONFIRM, interval=3):
                continue
            if self.appear_then_click(self.I_MSTART_CONFIRM2, interval=3):
                continue
            if self.appear_then_click(self.I_MCONINUE, interval=3):
                continue
        logger.info("Start Roguelike")
        while 1:
            self.screenshot()
            if self.appear(self.I_M_STORE):
                break
            if self.appear_then_click(self.I_MFIRST_SKILL, interval=1):
                continue
        # 选中第一个柔风
        logger.info("Select first skill")

    def island_name(self) -> MoonSeaType:
        while 1:
            self.screenshot()
            text = self.O_ISLAND_NAME.ocr(self.device.image)
            if '星' in text:
                return MoonSeaType.island105
            if '战' in text:
                return MoonSeaType.island104
            if '混' in text:
                return MoonSeaType.island103
            if '神秘' in text:
                return MoonSeaType.island102
            if '宁息' in text:
                return MoonSeaType.island101

    def boss_team_lock(self):
        while 1:
            self.screenshot()
            if self.appear(self.I_BOSS_TEAM_LOCK):
                break
            if self.appear_then_click(self.I_BOSS_TEAM_UNLOCK, interval=2):
                logger.info('Click lock Boss Team')
                continue

    def boss_battle(self) -> bool:
        logger.hr('Boss Battle')
        self.ui_click_until_disappear(self.I_BOSS_FIRE, interval=1)
        self.device.stuck_record_clear()
        self.device.stuck_record_add('BATTLE_STATUS_S')
        while 1:
            self.screenshot()
            if self.appear(self.I_BOSS_SHARE):
                break
            if self.appear(self.I_BOSS_BATTLE_GIVEUP):
                # 打boss失败了
                logger.warning('Boss battle give up')
                self.ui_click_until_disappear(self.I_BOSS_BATTLE_GIVEUP, interval=1)
                continue

            if self.appear(self.I_BOSS_USE_DOUBLE, interval=1):
                # 双倍奖励
                logger.info('Double reward')
                self.ui_get_reward(self.I_BOSS_USE_DOUBLE)
            if self.ui_reward_appear_click():
                continue
            if self.appear_then_click(self.I_BOSS_GET_EXP, interval=1):
                logger.info('Get EXP')
                continue
            if self.appear_then_click(self.I_UI_CANCEL, interval=1):
                # 取消购买 万相赐福
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1):
                continue
            if self.appear_then_click(self.I_BOSS_SKIP, interval=1):
                # 第二个boss
                self.device.stuck_record_clear()
                self.device.stuck_record_add('BATTLE_STATUS_S')
                continue
        logger.info('Boss battle end')
        if self.wait_until_appear(self.I_BOSS_SHUTU, wait_time=20):
            self.ui_click(self.I_BOSS_SHUTU, stop=self.I_MSTART)
        return True


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = MoonSea(c, d)
    t.screenshot()

    t.one()
