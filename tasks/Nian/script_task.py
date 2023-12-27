# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
from datetime import timedelta, datetime, time
from cached_property import cached_property

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_team
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Nian.assets import NianAssets
from tasks.Component.GeneralBuff.config_buff import BuffClass

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer


class ScriptTask(GameUi, GeneralBattle, GeneralRoom, GeneralInvite, NianAssets):

    def run(self) -> None:
        def cd_exit(cd: timedelta=False):
            logger.warning(f'Nian in CD {cd}')
            if cd is False:
                self.set_next_run(task='Nian', success=False, finish=True)
                raise TaskEnd('Nian')
            next_run = datetime.now() + cd
            self.set_next_run(task='Nian', success=False, finish=False, target=next_run)
            raise TaskEnd('Nian')

        self.ui_get_current_page()
        self.ui_goto(page_team)
        con = self.config.nian.nian_config

        # 进入
        self.ui_get_current_page()
        self.ui_goto(page_team)
        self.check_zones('年兽')
        cd = self.check_cd()
        if cd:
            cd_exit(cd)
        # 但是这个时候还不一定可以完全判断有没有进入cd
        cd_count = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_N_WAITING):
                break
            if cd_count >= 4:
                # 4 x 1.5 = 6秒没有进入说明是在冷却中
                cd_exit()
            if self.appear_then_click(self.I_GR_AUTO_MATCH, interval=1.5):
                cd_count += 1
                continue
        # 匹配个8分钟，要是八分钟还没人拿没啥了
        logger.info('Waiting for match')
        click_timer = Timer(240)
        check_timer = Timer(480)
        click_timer.start()
        check_timer.start()
        self.device.stuck_record_add('LOGIN_CHECK')
        while 1:
            self.screenshot()
            # 如果被秒开进入战斗, 被秒开不支持开启buff
            if self.check_take_over_battle(False, config=self.battle_config):
                logger.info('Nian take over battle')
                break
            # 如果进入房间
            elif self.is_in_room():
                self.device.stuck_record_clear()
                if self.wait_battle(wait_time=time(minute=1)):
                    buff = []
                    if con.buff_gold_50_click:
                        buff.append(BuffClass.GOLD_50)
                    if con.buff_gold_100_click:
                        buff.append(BuffClass.GOLD_100)
                    if buff is []:
                        buff = None
                    self.run_general_battle(config=self.battle_config, buff=buff)
                    # 打完后返回庭院，记得关闭buff
                    self.open_buff()
                    if con.buff_gold_50_click:
                        self.gold_50(False)
                    if con.buff_gold_100_click:
                        self.gold_100(False)
                    self.close_buff()
                    break
                else:
                    break
            # 如果时间到了
            if click_timer and click_timer.reached():
                logger.warning('It has waited for 240s , but the battle has not started.')
                logger.warning('It will be waited for 240s and try again.')
                self.screenshot()
                self.click(self.C_CLIC_SAFE)
                click_timer = None
                self.device.stuck_record_clear()
                self.device.stuck_record_add('LOGIN_CHECK')
                continue

            if check_timer.reached():
                logger.warning('Nian match timeout')
                while 1:
                    self.screenshot()
                    if not self.appear(self.I_N_WAITING):
                        break
                    if self.appear_then_click(self.I_N_WAITING, interval=0.7):
                        continue
                logger.info('Nian match timeout, exit')
                break
            # 如果还在匹配中
            if self.appear(self.I_N_WAITING):
                continue

        # 退出结束
        self.set_next_run(task='Nian', success=True, finish=False)
        raise TaskEnd('Nian')

    def check_cd(self) -> False or timedelta:
        """
        检查是否在冷却中,
        :return: 如果是冷却中, 返回剩余时间, 否则返回False
        """
        self.screenshot()
        if not self.appear(self.I_N_CHECK):
            return False
        if not self.ocr_appear(self.O_N_BATTLE_AGAIN):
            return False
        # 可以判断是在冷却了
        result = self.O_N_CD.ocr(self.device.image)
        if not isinstance(result, str):
            logger.error(f'OCR error {result}')
            return False
        try:
            result = re.search(r'(\d+)时(\d+)分后可', result)
            time_delta = timedelta(hours=int(result.group(1)), minutes=int(result.group(2)))
        except Exception as e:
            logger.error(f'{e} {result}')
            time_delta = timedelta(hours=4)
        return time_delta

    @cached_property
    def battle_config(self) -> GeneralBattleConfig:
        conf = GeneralBattleConfig()
        return conf

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()


