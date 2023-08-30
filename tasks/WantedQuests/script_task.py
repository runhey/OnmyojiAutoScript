# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
import copy
from time import sleep
from datetime import timedelta, time, datetime
from cached_property import cached_property

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_exploration
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Secret.script_task import ScriptTask as SecretScriptTask
from tasks.WantedQuests.config import WantedQuestsConfig
from tasks.WantedQuests.assets import WantedQuestsAssets

class ScriptTask(SecretScriptTask, GeneralInvite, WantedQuestsAssets):

    def run(self):
        con = self.config
        self.pre_work()
        self.screenshot()
        number_challenge = self.O_WQ_NUMBER.ocr(self.device.image)
        O_TEXT_COPY_1 = copy.deepcopy(self.O_WQ_TEXT_1)
        O_TEXT_COPY_2 = copy.deepcopy(self.O_WQ_TEXT_2)
        O_TEXT_COPY_1.keyword = '封印'
        O_TEXT_COPY_2.keyword = '封印'
        ocr_error_count = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_WQ_BOX):
                self.ui_get_reward(self.I_WQ_BOX)
                continue
            if ocr_error_count > 10:
                logger.warning('OCR failed too many times, exit')
                break
            if self.ocr_appear(self.O_WQ_TEXT_1, interval=0.7) or self.ocr_appear(O_TEXT_COPY_1, interval=0.7):
                cu, re, total = self.O_WQ_NUM_1.ocr(self.device.image)
                if cu == re == total == 0:
                    logger.warning('OCR failed and skip this round')
                    ocr_error_count += 1
                if cu > total:
                    logger.warning('Current number of wanted quests is greater than total number')
                    cu = cu % 10
                if cu < total and re != 0:
                    self.execute_mission(self.O_WQ_TEXT_1, total, number_challenge)
                continue
            if self.ocr_appear(self.O_WQ_TEXT_2, interval=0.7) or self.ocr_appear(O_TEXT_COPY_1, interval=0.7):
                cu, re, total = self.O_WQ_NUM_2.ocr(self.device.image)
                if cu == re == total == 0:
                    logger.warning('OCR failed and skip this round')
                    ocr_error_count += 1
                if cu > total:
                    logger.warning('Current number of wanted quests is greater than total number')
                    cu = cu % 10
                if cu < total and re != 0:
                    self.execute_mission(self.O_WQ_TEXT_2, total, number_challenge)
                continue

            if self.appear(self.I_WQ_CHECK_TASK):
                continue
            sleep(1.5)
            self.screenshot()
            if not self.appear(self.I_WQ_CHECK_TASK):
                logger.info('No wanted quests')
                break


        self.next_run()
        raise TaskEnd('WantedQuests')

    def next_run(self):
        before_end: time = self.config.wanted_quests.wanted_quests_config.before_end
        if before_end == time(hour=0, minute=0, second=0):
            self.set_next_run(task='WantedQuests', success=True, finish=True)
            return
        time_delta = timedelta(hours=-before_end.hour, minutes=-before_end.minute, seconds=-before_end.second)
        now_datetime = datetime.now()
        now_time = now_datetime.time()
        if time(hour=6) <= now_time < time(hour=18):
            # 如果是在6点到18点之间，那就设定下一次运行的时间为第二天的6点 + before_end
            next_run_datetime = datetime.combine(now_datetime.date() + timedelta(days=1), time(hour=6))
            next_run_datetime = next_run_datetime + time_delta
        elif time(hour=18) <= now_time < time(hour=23, minute=59, second=59):
            # 如果是在18点到23点59分59秒之间，那就设定下一次运行的时间为第二天的18点 + before_end
            next_run_datetime = datetime.combine(now_datetime.date() + timedelta(days=1), time(hour=18))
            next_run_datetime = next_run_datetime + time_delta
        else:
            # 如果是在0点到6点之间，那就设定下一次运行的时间为今天的18点 + before_end
            next_run_datetime = datetime.combine(now_datetime.date(), time(hour=18))
            next_run_datetime = next_run_datetime + time_delta
        self.set_next_run(task='WantedQuests', target=next_run_datetime)

    def pre_work(self):
        """
        前置工作，
        :return:
        """
        self.ui_get_current_page()
        self.ui_goto(page_main)
        while 1:
            self.screenshot()
            if self.appear(self.I_TARCE_DISENABLE):
                break
            if self.appear_then_click(self.I_WQ_SEAL, interval=1):
                continue
            if self.appear_then_click(self.I_WQ_DONE, interval=1):
                continue
            if self.appear_then_click(self.I_TRACE_ENABLE, interval=1):
                continue
        # 已追踪所有任务
        logger.info('All wanted quests are traced')
        self.invite_five()
        self.ui_click_until_disappear(self.I_UI_BACK_RED)
        self.ui_goto(page_exploration)

    def execute_mission(self, ocr, num_want: int, num_challenge: int):
        """

        :param ocr: 要点击的 文字
        :param num_want: 一共要打败的怪物数量
        :param num_challenge: 现在有的挑战卷数量
        :return:
        """
        logger.hr('Start wanted quests')
        while 1:
            self.screenshot()
            if self.appear(self.I_TRACE_TRUE):
                break
            if self.click(ocr, interval=1):
                continue
        if not self.appear(self.I_GOTO_1):
            # 如果没有出现 '前往'按钮， 那就是这个可能是神秘任务但是没有解锁
            logger.warning('This is a secret mission but not unlock')
            self.ui_click(self.I_TRACE_TRUE, self.I_TRACE_FALSE)
            return
        # 找到一个最优的关卡来挑战
        challenge = True if num_challenge >= 10 else False
        def check_battle(cha: bool, wq_type, wq_info) -> tuple:
            battle = False
            self.screenshot()
            type_wq = wq_type.ocr(self.device.image)
            if cha and type_wq == '挑战':
                battle = 'CHALLENGE'
            if type_wq == '秘闻':
                battle = 'SECRET'
            if not battle:
                return None, None
            info = wq_info.ocr(self.device.image)
            try:
                # 匹配： 第九章(数量:5)
                one_number = int(re.findall(r'(\d+)', info)[-1])
                # one_number = int(re.findall(r'\*\(\数量:\s*(\d+)\)', info)[0])
            except IndexError:
                # 匹配： 第九章
                one_number = 3
            # num_want / one_number = 一共要打几次
            if one_number > num_want:
                return battle, 1
            else:
                return battle, num_want // one_number + 1

        battle, num, goto = None, None, None
        if not battle:
            battle, num = check_battle(challenge, self.O_WQ_TYPE_1, self.O_WQ_INFO_1)
            goto = self.I_GOTO_1
        if not battle:
            battle, num = check_battle(challenge, self.O_WQ_TYPE_2, self.O_WQ_INFO_2)
            goto = self.I_GOTO_2
        if not battle:
            battle, num = check_battle(challenge, self.O_WQ_TYPE_3, self.O_WQ_INFO_3)
            goto = self.I_GOTO_3
        if not battle:
            battle, num = check_battle(challenge, self.O_WQ_TYPE_4, self.O_WQ_INFO_4)
            goto = self.I_GOTO_4
        if battle == 'CHALLENGE':
            self.challenge(goto, num)
        elif battle == 'SECRET':
            self.secret(goto, num)
        else:
            # 没有找到可以挑战的关卡 那就关闭
            logger.warning('No wanted quests can be challenged')
            return False


    def challenge(self, goto, num):
        self.ui_click(goto, self.I_WQC_FIRE)
        self.ui_click(self.I_WQC_LOCK, self.I_WQC_UNLOCK)
        self.ui_click_until_disappear(self.I_WQC_FIRE)
        self.run_general_battle()
        self.wait_until_appear(self.I_WQC_FIRE, wait_time=4)
        self.ui_click_until_disappear(self.I_UI_BACK_RED)
        # 我忘记了打完后是否需要关闭 挑战界面

    def secret(self, goto, num=1):
        self.ui_click(goto, self.I_WQSE_FIRE)
        for i in range(num):
            self.wait_until_appear(self.I_WQSE_FIRE)
            # self.ui_click_until_disappear(self.I_WQSE_FIRE)
            # 又臭又长的对话针的是服了这个网易
            click_count = 0
            while 1:
                self.screenshot()
                if not self.appear(self.I_UI_BACK_RED, threshold=0.7):
                    break
                if self.appear_then_click(self.I_WQSE_FIRE, interval=1):
                    continue
                if self.appear(self.I_UI_BACK_RED, threshold=0.7) and not self.appear(self.I_WQSE_FIRE):
                    self.click(self.C_SECRET_CHAT, interval=0.8)
                    click_count += 1
                    if click_count >= 6:
                        logger.warning('Secret mission chat too long, force to close')
                        click_count = 0
                        self.device.click_record_clear()
                    continue
            success = self.run_general_battle(self.battle_config)
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_EXPLORATION):
                break
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1):
                continue
            if self.appear_then_click(self.I_UI_BACK_BLUE, interval=1.5):
                continue
        logger.info('Secret mission finished')

    def invite_five(self):
        """
        邀请好友，默认点五个
        :return:
        """
        def invite(add_button):
            self.screenshot()
            if not self.appear(add_button):
                return False
            self.ui_click(add_button, self.I_INVITE_ENSURE)
            sleep(1)
            self.click(self.I_WQ_FIREND_1)
            sleep(0.4)
            self.click(self.I_WQ_FIREND_2)
            sleep(0.4)
            self.click(self.I_WQ_FIREND_3)
            sleep(0.4)
            self.click(self.I_WQ_FIREND_4)
            sleep(0.4)
            self.click(self.I_WQ_FIREND_5)
            sleep(0.2)
            self.screenshot()
            if not self.appear(self.I_SELECTED):
                logger.warning('No friend selected')
                return False
            self.ui_click_until_disappear(self.I_INVITE_ENSURE)
            sleep(0.5)

        logger.hr('Invite friends')
        invite(self.I_WQ_INVITE_1)
        invite(self.I_WQ_INVITE_2)
        invite(self.I_WQ_INVITE_3)

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
    # print(t.appear(t.I_WQ_CHECK_TASK))



