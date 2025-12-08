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
            #self._check_first_priority_task()
            if cnt >= max_cont:
                logger.info('Run out of count, exit')
                break
            if datetime.now() - self.start_time >= max_time:
                logger.info('Run out of time, exit')
                break
            if self.one():
                cnt += 1
                logger.info(f'Run {cnt} times')
            else:
                break
        self.push_notify(content=f'任务已完成{cnt}次,用时: {timedelta(seconds=int((datetime.now() - self.start_time).total_seconds()))}')
        logger.info('Exit Moon Sea')

    def one(self):
        self.cnt_skill101 = 0
        self.cnt_skillpower = 1
        if not self._start():
            return False
        while 1:
            self.screenshot()

            # if self.activate_store():
            #     continue

            # 如果是boss
            
                

            if self.select_skill(refresh=True):
                continue

            if self.enter_island():
                continue
            isl_type = self.island_name()
            if not isl_type:
                continue
            match isl_type:
                case MoonSeaType.island101: self.run_l101()
                case MoonSeaType.island102: self.run_l102()
                case MoonSeaType.island103: self.run_103()
                case MoonSeaType.island104: self.run_l104()
                case MoonSeaType.island105: self.run_l105()
                case MoonSeaType.island106:
                    logger.info('Is boss island')
                    self.boss_team_lock()
                    if self.boss_battle():
                        return True
                    else:
                        continue
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
            if self.appear(self.I_MSTART,interval=1):
                if self._conf.number_enable:
                    cu = self.O_SIXREALMS_NUMBER.ocr(self.device.image)
                    logger.info(f"六道门票数量：{cu}")
                    if not cu > 0:
                        self.push_notify("六道门票数量不足, 退出！")
                        return False
                break
            if self.appear_then_click(self.I_MENTER, interval=1):
                continue
            if self.appear(self.I_MCONINUE):
                # 继续上一把的
                self.ui_click_until_disappear(self.I_MCONINUE)
                return True
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
            if self.appear_then_click(self.I_MPEACOCK_SKILL, interval=3):
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
        return True

    def island_name(self):
        while 1:
            self.screenshot()
            text = self.O_ISLAND_NAME.ocr(self.device.image)
            if '绽放' in text:
                return MoonSeaType.island105
            if '战之' in text:
                return MoonSeaType.island104
            if '混' in text:
                return MoonSeaType.island103
            if '神秘' in text:
                return MoonSeaType.island102
            if '宁息' in text:
                return MoonSeaType.island101
            if '恋色' in text:
                return MoonSeaType.island106
            else:
                return False

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
        self.save_image()
        if self.wait_until_appear(self.I_BOSS_SHUTU, wait_time=20):
            self.ui_click(self.I_BOSS_SHUTU, stop=self.I_MSTART)
        return True


if __name__ == '__main__':
    from module.config.config import Config

    c = Config('du')
    t = MoonSea(c)
    t.one()
    # t.select_skill()
