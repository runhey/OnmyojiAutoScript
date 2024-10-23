# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
import copy
from time import sleep
from datetime import timedelta, time, datetime
from cached_property import cached_property
from enum import Enum
from module.atom.image import RuleImage

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_exploration, page_shikigami_records
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Secret.script_task import ScriptTask as SecretScriptTask
from tasks.WantedQuests.config import WantedQuestsConfig, CooperationType, CooperationSelectMask, \
    CooperationSelectMaskDescription
from tasks.WantedQuests.assets import WantedQuestsAssets
from tasks.WantedQuests.explore import WQExplore, ExploreWantedBoss
from tasks.Component.Costume.config import MainType
from typing import List
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul


class ScriptTask(WQExplore, SecretScriptTask, WantedQuestsAssets):
    want_strategy_excluding: list[list] = []  # 不需要执行的

    def run(self):
        con = self.config.model.wanted_quests
        # 自动换御魂
        if con.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(con.switch_soul_config.switch_group_team)
        if con.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(con.switch_soul_config.group_name, con.switch_soul_config.team_name)

        if not self.pre_work():
            # 无法完成预处理 很有可能你已经完成了悬赏任务
            logger.warning('Cannot pre-work')
            logger.warning('You may have completed the reward task')
            self.next_run()
            raise TaskEnd('WantedQuests')

        self.screenshot()
        number_challenge = self.O_WQ_NUMBER.ocr(self.device.image)
        ocr_error_count = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_WQ_BOX):
                self.ui_get_reward(self.I_WQ_BOX)
                continue
            if ocr_error_count > 10:
                logger.warning('OCR failed too many times, exit')
                break
            if self.ocr_appear(self.O_WQ_TEXT_1, interval=1):
                cu, re, total = self.O_WQ_NUM_1.ocr(self.device.image)
                if cu == re == total == 0:
                    logger.warning('OCR failed and have a try')
                    ocr_error_count += 1
                    # 尝试打一次
                    unknown_num = self.O_WQ_NUM_UNKNOWN_1.ocr(self.device.image)
                    if unknown_num > 14:
                        self.execute_mission(self.O_WQ_TEXT_1, 1, number_challenge)
                if cu > total:
                    logger.warning('Current number of wanted quests is greater than total number')
                    cu = cu % 10
                if cu < total and re != 0:
                    self.execute_mission(self.O_WQ_TEXT_1, min(total, 20), number_challenge)

            if self.ocr_appear(self.O_WQ_TEXT_2, interval=1):
                cu, re, total = self.O_WQ_NUM_2.ocr(self.device.image)
                if cu == re == total == 0:
                    logger.warning('OCR failed and have a try')
                    ocr_error_count += 1
                    # 尝试打一次
                    unknown_num = self.O_WQ_NUM_UNKNOWN_2.ocr(self.device.image)
                    if unknown_num > 14:
                        self.execute_mission(self.O_WQ_TEXT_2, 1, number_challenge)
                if cu > total:
                    logger.warning('Current number of wanted quests is greater than total number')
                    cu = cu % 10
                if cu < total and re != 0:
                    self.execute_mission(self.O_WQ_TEXT_2, min(total, 20), number_challenge)
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
            # 如果是在6点到18点之间，那就设定下一次运行的时间为第二天的0点非6点 + before_end
            next_run_datetime = datetime.combine(now_datetime.date() + timedelta(days=1), time(hour=0))
            next_run_datetime = next_run_datetime + time_delta
        elif time(hour=18) <= now_time < time(hour=23, minute=59, second=59):
            # 如果是在18点到23点59分59秒之间，那就设定下一次运行的时间为第二天的18点 + before_end
            next_run_datetime = datetime.combine(now_datetime.date() + timedelta(days=1), time(hour=18))
            next_run_datetime = next_run_datetime + time_delta
        else:
            # 如果是在0点到5点之间，那就设定下一次运行的时间为今天的18点 + before_end
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
        done_timer = Timer(5)
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
            if self.special_main and self.click(self.C_SPECIAL_MAIN, interval=3):
                logger.info('Click special main left to find wanted quests')
                continue
            if self.appear(self.I_UI_BACK_RED):
                if not done_timer.started():
                    done_timer.start()
            if done_timer.started() and done_timer.reached():
                self.ui_click_until_disappear(self.I_UI_BACK_RED)
                return False
        # 已追踪所有任务
        logger.info('All wanted quests are traced')

        # 存在协作任务则邀请
        self.screenshot()
        if self.appear(self.I_WQ_INVITE_1) or self.appear(self.I_WQ_INVITE_2) or self.appear(self.I_WQ_INVITE_3):
            if self.config.wanted_quests.wanted_quests_config.invite_friend_name:
                self.all_cooperation_invite(self.config.wanted_quests.wanted_quests_config.invite_friend_name)
            else:
                self.invite_five()
        self.ui_click_until_disappear(self.I_UI_BACK_RED)
        self.ui_goto(page_exploration)
        return True

    def execute_mission(self, ocr, num_want: int, num_challenge: int):
        """

        :param ocr: 要点击的 文字
        :param num_want: 一共要打败的怪物数量
        :param num_challenge: 现在有的挑战卷数量
        :return:
        """
        OCR_WQ_TYPE = [self.O_WQ_TYPE_1, self.O_WQ_TYPE_2, self.O_WQ_TYPE_3, self.O_WQ_TYPE_4]
        OCR_WQ_INFO = [self.O_WQ_INFO_1, self.O_WQ_INFO_2, self.O_WQ_INFO_3, self.O_WQ_INFO_4]
        GOTO_BUTTON = [self.I_GOTO_1, self.I_GOTO_2, self.I_GOTO_3, self.I_GOTO_4]

        def extract_info(index: int) -> tuple or None:
            """
            提取每一个地点的信息
            :param index: 从零开始
            :return:
            (type, destination, number, goto_button)
            (类型, 地点层级，可以打败的数量，前往按钮)
            类型： 挑战0, 秘闻1， 探索2
            """
            layer_limit = {
                # 低层不限制
                # "壹", "贰", "叁", "肆", "伍", "陆",
                "柒", "捌", "玖", "拾"
            }
            result = [-1, '', -1, GOTO_BUTTON[index]]
            type_wq = OCR_WQ_TYPE[index].ocr(self.device.image)
            info_wq_1 = OCR_WQ_INFO[index].ocr(self.device.image)
            info_wq_1 = info_wq_1.replace('：', ':').replace('（', '(').replace('）', ')')
            info_wq_1 = info_wq_1.replace('：', ':')
            match = re.match(r"^(.*?)\(数量:\s*(\d+)\)", info_wq_1)
            if not match:
                return None
            wq_destination = match.group(1)
            wq_number = int(match.group(2))
            # 跳过高层秘闻
            if wq_destination[-1] in layer_limit:
                logger.warning('This secret layer is too high')
                return None
            result[1] = wq_destination
            result[2] = wq_number
            order_list = self.config.model.wanted_quests.wanted_quests_config.battle_priority
            order_list = order_list.replace(' ', '').replace('\n', '')
            order_list: list = re.split(r'>', order_list)
            result[0] = order_list.index(type_wq) if type_wq in order_list else -1
            # if type_wq == '挑战':
            #     result[0] = 0 if num_challenge >= 10 else -1
            # elif type_wq == '秘闻':
            #     result[0] = 1
            # elif type_wq == '探索':
            #     result[0] = 2
            logger.info(f'[Wanted Quests] type: {type_wq} destination: {wq_destination} number: {wq_number} ')
            return tuple(result) if result[0] != -1 else None

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
            return False

        info_wq_list = []
        for i in range(4):
            info_wq = extract_info(i)
            if info_wq:
                info_wq_list.append(info_wq)
        info_wq_list = [item for item in info_wq_list if item not in self.want_strategy_excluding]
        if not info_wq_list:
            logger.warning('No wanted quests can be challenged')
            return False
        # sort
        info_wq_list.sort(key=lambda x: x[0])
        best_type, destination, once_number, goto_button = info_wq_list[0]
        do_number = 1 if once_number >= num_want else num_want // once_number + (1 if num_want % once_number > 0 else 0)
        try:
            match best_type:
                case 0:
                    self.challenge(goto_button, do_number)
                case 1:
                    self.secret(goto_button, do_number)
                case 2:
                    self.explore(goto_button, do_number)
                case _:
                    logger.warning('No wanted quests can be challenged')
        except ExploreWantedBoss:
            logger.warning('The extreme case. The quest only needs to challenge one final boss, so skip it')
            self.want_strategy_excluding.append(info_wq_list[0])

    def challenge(self, goto, num):
        self.ui_click(goto, self.I_WQC_FIRE)
        self.ui_click(self.I_WQC_UNLOCK, self.I_WQC_LOCK)
        self.ui_click_until_disappear(self.I_WQC_FIRE)
        # 锁定阵容进入战斗
        wq_config = GeneralBattleConfig(lock_team_enable=True)
        self.run_general_battle(config=wq_config)
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

    def invite_random(self, add_button: RuleImage):
        self.screenshot()
        if not self.appear(add_button):
            return False
        self.ui_click(add_button, self.I_WQ_INVITE_ENSURE, interval=2.5)
        logger.info('enter invite form')
        sleep(1)
        self.click(self.I_WQ_FRIEND_1)
        sleep(0.4)
        self.click(self.I_WQ_FRIEND_2)
        sleep(0.4)
        self.click(self.I_WQ_FRIEND_3)
        sleep(0.4)
        self.click(self.I_WQ_FRIEND_4)
        sleep(0.4)
        self.click(self.I_WQ_FRIEND_5)
        sleep(0.2)
        self.screenshot()
        if not self.appear(self.I_SELECTED):
            logger.warning('No friend selected')
            return False
        self.ui_click_until_disappear(self.I_INVITE_ENSURE)
        sleep(0.5)

    def invite_five(self):
        """
        邀请好友，默认点五个
        :return:
        """

        logger.hr('Invite friends')
        self.invite_random(self.I_WQ_INVITE_1)
        self.invite_random(self.I_WQ_INVITE_2)
        self.invite_random(self.I_WQ_INVITE_3)

    def all_cooperation_invite(self, name: str):
        """
            所有的协作任务依次邀请
        @param name: 被邀请的朋友名
        @return:

        """
        self.screenshot()
        if not self.appear(self.I_WQ_INVITE_1):
            return False

        ret = self.get_cooperation_info()
        if len(ret) == 0:
            logger.info("no Cooperation found")
            return False
        typeMask = 15
        typeMask = CooperationSelectMask[self.config.wanted_quests.wanted_quests_config.cooperation_type.value]
        for item in ret:
            # 该任务是需要邀请的任务类型
            if not (item['type'] & typeMask):
                # BUG 存在多个协作任务时,邀请完第一个协作任务对方接受后,未邀请的任务位置无法确定(缺少信息)
                # 例如 按顺序存在 abc 3个协作任务,邀请完a,好友接受后,这三个任务在界面上的顺序变化,abc 还是bca
                # 如果顺序不变 则应该没有问题
                logger.info("cooperationType %s But needed Type %s ,Skipped", item['type'], typeMask)
                break
            '''
               尝试5次 如果邀请失败 等待20s 重新尝试
               阴阳师BUG: 好友明明在线 但邀请界面找不到该好友(好友未接受任何协作任务的情况下)
           '''
            index = 0
            while index < 5:
                if self.cooperation_invite(item['inviteBtn'], name):
                    item['inviteResult'] = True
                    index = 5
                logger.info("%s not found,Wait 20s,%d invitations left", name, 5 - index - 1)
                index += 1
                sleep(20) if index < 5 else sleep(0)
                # NOTE 等待过程如果出现协作邀请 将会卡住 为了防止卡住
                self.screenshot()
        return ret

    def cooperation_invite(self, btn: RuleImage, name: str):
        """
            单个协作任务邀请
        @param btn:
        @param name:
        @return:
        """
        self.ui_click(btn, self.I_WQ_INVITE_ENSURE, interval=2.5)

        # 选人
        self.O_WQ_INVITE_COLUMN_1.keyword = name
        self.O_WQ_INVITE_COLUMN_2.keyword = name

        find = False
        for i in range(2):
            self.screenshot()
            in_col_1 = self.ocr_appear_click(self.O_WQ_INVITE_COLUMN_1)
            in_col_2 = self.ocr_appear_click(self.O_WQ_INVITE_COLUMN_2)
            find = in_col_2 or in_col_1
            if find:
                self.screenshot()
                if self.appear(self.I_WQ_INVITE_SELECTED):
                    logger.info("friend found and selected")
                    break
                # TODO OCR识别到文字 但是没有选中 尝试重新选择  (选择好友时,弹出协作邀请导致选择好友失败)
            # 在当前服务器没找到,切换服务器
            self.click(self.I_WQ_INVITE_DIFF_SVR)
            # NOTE 跨服好友刷新缓慢,切换标签页难以检测,姑且用延时.非常卡的模拟器可能出问题
            sleep(2)
        # 没有找到需要邀请的人,点击取消 返回悬赏封印界面
        if not find:
            self.screenshot()
            self.click(self.I_WQ_INVITE_CANCEL)
            return False
        #
        self.ui_click_until_disappear(self.I_WQ_INVITE_ENSURE)
        return True

    def get_cooperation_info(self) -> List:
        """
            获取协作任务详情
        @return: 协作任务类型与邀请按钮
        """
        self.screenshot()
        retList = []
        i = 0
        for index in range(3):
            btn = self.__getattribute__("I_WQ_INVITE_" + str(index + 1))
            if not self.appear(btn):
                break
            if self.appear(self.__getattribute__("I_WQ_COOPERATION_TYPE_JADE_" + str(index + 1))):
                retList.append({'type': CooperationType.Jade, 'inviteBtn': btn})
                continue
            if self.appear(self.__getattribute__("I_WQ_COOPERATION_TYPE_DOG_FOOD_" + str(index + 1))):
                retList.append({'type': CooperationType.Food, 'inviteBtn': btn})
                continue
            if self.appear(self.__getattribute__("I_WQ_COOPERATION_TYPE_CAT_FOOD_" + str(index + 1))):
                retList.append({'type': CooperationType.Food, 'inviteBtn': btn})
                continue
            if self.appear(self.__getattribute__("I_WQ_COOPERATION_TYPE_SUSHI_" + str(index + 1))):
                retList.append({'type': CooperationType.Sushi, 'inviteBtn': btn})
                continue
            # NOTE 因为食物协作里面也有金币奖励 ,所以判断金币协作放在最后面
            if self.appear(self.__getattribute__("I_WQ_COOPERATION_TYPE_GOLD_" + str(index + 1))):
                retList.append({'type': CooperationType.Gold, 'inviteBtn': btn})
                continue

        return retList

    @cached_property
    def special_main(self) -> bool:
        # 特殊的庭院需要点一下，左边然后才能找到图标
        main_type = self.config.global_game.costume_config.costume_main_type
        if main_type == MainType.COSTUME_MAIN_3:
            return True
        return False


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()


