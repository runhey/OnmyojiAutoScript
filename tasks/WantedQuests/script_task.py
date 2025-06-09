# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta, time, datetime
from time import sleep
from typing import List

import re
import cv2
from cached_property import cached_property

from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr
from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger
from tasks.Component.Costume.config import MainType
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.GameUi.page import page_main, page_exploration, page_shikigami_records
from tasks.Secret.script_task import ScriptTask as SecretScriptTask
from tasks.WantedQuests.assets import WantedQuestsAssets
from tasks.WantedQuests.config import CooperationType, CooperationSelectMask
from tasks.WantedQuests.explore import WQExplore, ExploreWantedBoss


class ScriptTask(WQExplore, SecretScriptTask, WantedQuestsAssets):
    want_strategy_excluding: list[list] = []  # 不需要执行的
    # 追踪界面(显示"前往"按钮的界面,左上角位置,神秘任务不好使)显示以下名称时,任务不再执行
    unwanted_boss_name_list: list = []

    def run(self):
        con = self.config.model.wanted_quests
        unwanted_boss_names = con.wanted_quests_config.unwanted_boss_names
        if unwanted_boss_names is not None and unwanted_boss_names != '':
            import re
            self.unwanted_boss_name_list = re.split(r"[，,]", unwanted_boss_names)

        # 自动换御魂
        if con.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(con.switch_soul_config.switch_group_team)
        if con.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(con.switch_soul_config.group_name, con.switch_soul_config.team_name)

        preSuc = False
        if (self.get_config()).cooperation_only:
            preSuc = self.pre_work_cooperation_only()
        else:
            preSuc = self.pre_work()
        if not preSuc:
            # 无法完成预处理 很有可能你已经完成了悬赏任务
            logger.warning('Cannot pre-work')
            logger.warning('You may have completed the reward task')
            self.next_run()
            raise TaskEnd('WantedQuests')

        self.screenshot()
        number_challenge = self.O_WQ_NUMBER.ocr(self.device.image)
        error_count = 0
        while 1:
            self.screenshot()
            if not self.is_wq_remained():
                logger.info("no more wq remained")
                break
            if self.appear(self.I_WQ_BOX):
                logger.info("get reward")
                self.ui_get_reward(self.I_WQ_BOX)
                continue
            if self.appear(self.I_TREASURE_BOX_CLICK):
                logger.info("get treasure")
                self.ui_get_reward(self.I_TREASURE_BOX_CLICK)
                continue
            if error_count > 3:
                logger.warning('failed too many times, exit')
                break
            cu, re, total, area = self.find_wq(self.device.image)
            if re == -1:
                error_count += 1
                # 没找到任务 尝试上滑
                self.swipe(self.S_WQ_LIST_UP, interval=1)
                sleep(1)
                continue
            # 找到任务,执行
            error_count=0
            self.O_WQ_TEXT_ALL.area = area
            self.execute_mission(self.O_WQ_TEXT_ALL, total - cu, number_challenge)
            sleep(1.5)



        # region 旧代码
        # # 第一个位置
        # wq_1_done = False
        # wq_2_done = False
        # while 1:
        #     self.screenshot()
        #     if self.appear(self.I_WQ_BOX):
        #         self.ui_get_reward(self.I_WQ_BOX)
        #         continue
        #     if self.appear(self.I_TREASURE_BOX_CLICK):
        #         self.ui_get_reward(self.I_TREASURE_BOX_CLICK)
        #         continue
        #     if ocr_error_count > 10:
        #         logger.warning('OCR failed too many times, exit')
        #         break
        #     # if self.ocr_appear(self.O_WQ_TEXT_1, interval=1):
        #     if (not wq_1_done) and self.txt_ocr_appear(self.O_WQ_TEXT_1, r".*[封|野]印.*", self.device.image):
        #         # cu, re, total = self.O_WQ_NUM_1.ocr(self.device.image)
        #         cu, re, total = self.process_ocr(self.O_WQ_NUM_1, self.device.image)
        #         if cu == re == total == 0:
        #             logger.warning('OCR failed and have a try')
        #             ocr_error_count += 1
        #             # 尝试打一次
        #             unknown_num = self.O_WQ_NUM_UNKNOWN_1.ocr(self.device.image)
        #             if unknown_num > 14:
        #                 self.execute_mission(self.O_WQ_TEXT_1, 1, number_challenge)
        #         if total > 14:
        #             logger.warning("Total number of wanted quests is greater than 14")
        #             total = total % 10
        #         if cu > total:
        #             logger.warning('Current number of wanted quests is greater than total number')
        #             cu = cu % 10
        #         if cu < total and re != 0:
        #             self.execute_mission(self.O_WQ_TEXT_1, min(total - cu, 20), number_challenge)
        #         if cu == total:
        #             wq_1_done = True
        #
        #     # if self.ocr_appear(self.O_WQ_TEXT_2, interval=1):
        #     if self.txt_ocr_appear(self.O_WQ_TEXT_2, r".*[封|野]印.*", self.device.image):
        #         # cu, re, total = self.O_WQ_NUM_2.ocr(self.device.image)
        #         cu, re, total = self.process_ocr(self.O_WQ_NUM_2, self.device.image)
        #         if cu == re == total == 0:
        #             logger.warning('OCR failed and have a try')
        #             ocr_error_count += 1
        #             # 尝试打一次
        #             unknown_num = self.O_WQ_NUM_UNKNOWN_2.ocr(self.device.image)
        #             if unknown_num > 14:
        #                 self.execute_mission(self.O_WQ_TEXT_2, 1, number_challenge)
        #         if total > 14:
        #             logger.warning("Total number of wanted quests is greater than 14")
        #             total = total % 10
        #         if cu > total:
        #             logger.warning('Current number of wanted quests is greater than total number')
        #             cu = cu % 10
        #         if cu < total and re != 0:
        #             self.execute_mission(self.O_WQ_TEXT_2, min(total - cu, 20), number_challenge)
        #         continue
        #
        #     # 妖气封印或者年兽，那就四分钟后继续
        #     if self.appear(self.I_WQ_D1111) or self.appear(self.I_WQ_NIAN):
        #         logger.warning('Tiger is in the way, wait for 4 minutes')
        #         logger.info('Time to wait for 4 minutes')
        #         self.set_next_run('WantedQuests', target=datetime.now() + timedelta(minutes=4))
        #         raise TaskEnd('WantedQuests')
        #     if self.appear(self.I_WQ_CHECK_TASK):
        #         continue
        #     sleep(1.5)
        #     self.screenshot()
        #     if not self.appear(self.I_WQ_CHECK_TASK):
        #         logger.info('No wanted quests')
        #         break
        # endregion

        self.next_run()
        raise TaskEnd('WantedQuests')

    def next_run(self):
        before_end: time = self.get_config().before_end
        if before_end == time(hour=0, minute=0, second=0):
            self.set_next_run(task='WantedQuests', success=True, finish=True)
            return
        time_delta = timedelta(hours=-before_end.hour, minutes=-before_end.minute, seconds=-before_end.second)
        now_datetime = datetime.now()
        now_time = now_datetime.time()
        if time(hour=5) <= now_time < time(hour=18):
            # 如果是在5点到18点之间，那就设定下一次运行的时间为第二天的5点 + before_end
            next_run_datetime = datetime.combine(now_datetime.date() + timedelta(days=1), time(hour=5))
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
            if self.appear(self.I_TRACE_DISABLE):
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
            if self.need_invite_vip():
                self.all_cooperation_invite()
            else:
                self.invite_five()
        self.ui_click_until_disappear(self.I_UI_BACK_RED)
        self.ui_goto(page_exploration)
        return True

    def pre_work_cooperation_only(self):
        #
        if self.ui_get_current_page() != page_main:
            self.ui_goto(page_main)
        # 打开悬赏封印 界面
        done_timer = Timer(5)
        while 1:
            self.screenshot()
            if self.appear(self.I_TRACE_ENABLE) or self.appear(self.I_TRACE_DISABLE):
                break
            if self.appear_then_click(self.I_WQ_SEAL, interval=1):
                continue
            if self.appear_then_click(self.I_WQ_DONE, interval=1):
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
        #
        if not (self.appear(self.I_WQ_INVITE_1) or self.appear(self.I_WQ_INVITE_2) or self.appear(self.I_WQ_INVITE_3)):
            logger.info("there is no cooperation quest")
            return False

        # if self.appear(self.I_WQ_INVITE_1):
        #     self.trace_one(self.I_WQ_INVITE_1)
        # if self.appear(self.I_WQ_INVITE_2):
        #     self.trace_one(self.I_WQ_INVITE_2)
        # if self.appear(self.I_WQ_INVITE_3):
        #     self.trace_one(self.I_WQ_INVITE_3)

        # 追踪任务 并邀请
        self.all_cooperation_invite()

        self.ui_click_until_disappear(self.I_UI_BACK_RED)
        self.ui_goto(page_exploration)
        return True

    def trace_one(self, btn: RuleImage):
        """
            参数必须为邀请按钮(I_WQ_INVITE_n ),特定场景,就不做通用的函数了,怪麻烦的,若还有什么奇葩需求,再扩展吧
        @param btn: 邀请按钮,
        @type btn:
        """
        self.screenshot()
        if not self.appear(btn):
            return
        while 1:
            self.screenshot()
            # 追踪成功  或  是现世任务 不需要追踪
            if self.appear(self.I_WQ_TRACE_ONE_ENABLE) or self.appear(self.I_WQ_TRACE_ONE_REALWORLD):
                break
            if self.appear(self.I_WQ_TRACE_ONE_DISABLE):
                self.click(self.I_WQ_TRACE_ONE_DISABLE, interval=1.5)
                continue
            # 根据邀请按钮位置生成 对应的点击位置 打开追踪界面
            # NOTE magic Number

            self.device.click(btn.roi_front[0], btn.roi_front[1] - 40, control_name=str(btn) + ' y-40')
            # 防止点击后界面来不及刷新
            sleep(1.5)
        # 关闭单个任务的追踪界面
        self.ui_click_until_smt_disappear(self.C_WQ_TRACE_ONE_CLOSE, stop=self.I_WQ_TRACE_ONE_CHECK_OPENED,
                                          interval=1.5)

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
        name_funcs: dict = {
            '挑战': self.challenge,
            '探索': self.explore,
            '秘闻': self.secret
        }

        def extract_info(index: int) -> tuple or None:
            """
            提取每一个地点的信息
            :param index: 从零开始
            :return:
            (type, destination, number, goto_button, func)
            (类型, 地点层级，可以打败的数量，前往按钮, func)
            类型： 挑战0, 秘闻1， 探索2
            """
            layer_limit = {
                # 低层不限制
                # "壹", "贰", "叁", "肆", "伍", "陆",
                "柒", "捌", "玖", "拾", "番外"
            }
            # ,荒川之怒·壹，4，前往按钮，function
            result = [-1, '', -1, GOTO_BUTTON[index], self.challenge, '']
            type_wq = OCR_WQ_TYPE[index].ocr(self.device.image)
            info_wq_1 = OCR_WQ_INFO[index].ocr(self.device.image)
            info_wq_1 = info_wq_1.replace('：', ':').replace('（', '(').replace('）', ')')
            info_wq_1 = info_wq_1.replace('：', ':')
            match = re.match(r"^(.*?)[（(]?数量[：:]\s*(\d+)[)）]", info_wq_1)
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
            result[4] = name_funcs.get(type_wq, lambda: logger.warning('No task can be challenged'))
            result[5] = type_wq
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
        # 跳过不想打的
        monster_name = self.O_WQ_MONSTER_TYPE.detect_text(self.device.image)
        if monster_name in self.unwanted_boss_name_list:
            #
            logger.warning(f'unwanted {monster_name}')
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
            self.ui_click(self.I_TRACE_TRUE, self.I_TRACE_FALSE)
            return False
        # sort
        info_wq_list.sort(key=lambda x: x[0])
        filtered = list(filter(lambda x: (x[5] == '秘闻' or x[5] == '挑战') and x[2] >= 3, info_wq_list))
        if not filtered and len(filtered) != 0:
            info_wq_list = filtered
        best_type, destination, once_number, goto_button, func, _ = info_wq_list[0]
        do_number = 1 if once_number >= num_want else num_want // once_number + (1 if num_want % once_number > 0 else 0)
        try:
            func(goto_button, do_number)
        except ExploreWantedBoss:
            logger.warning('The extreme case. The quest only needs to challenge one final boss, so skip it')
            self.want_strategy_excluding.append(info_wq_list[0])

    def challenge(self, goto_btn, num):
        self.ui_click(goto_btn, self.I_WQC_FIRE)
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

    def all_cooperation_invite(self, name_all: str = None):
        """
            所有的协作任务依次邀请
            如果配置了只完成协作任务 还会将该任务设置为追踪
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
        typeMask = CooperationSelectMask[(self.get_config()).cooperation_type.value]
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
            item['inviteResult'] = False
            if name_all is None:
                name = self.get_invite_vip_name(item['type'])
            else:
                name = name_all
            logger.warning("find cooperationType %s ,start invite %s", item['type'], name)
            while index < 5:
                if self.cooperation_invite(item['inviteBtn'], name):
                    item['inviteResult'] = True
                    index = 5
                    continue
                logger.info("%s not found,Wait 20s,%d invitations left", name, 5 - index - 1)
                index += 1
                sleep(20) if index < 5 else sleep(0)
                # NOTE 等待过程如果出现协作邀请 将会卡住 为了防止卡住
                self.screenshot()
            # 邀请追踪一起吧,只有邀请成功才追踪
            if item['inviteResult']:
                self.invite_success_callback(item['type'], name)
                if (self.get_config()).cooperation_only:
                    logger.info("start trace_one")
                    self.trace_one(item['inviteBtn'])
        return ret

    def cooperation_invite(self, btn: RuleImage, name: str):
        """
            单个协作任务邀请
        @param btn:
        @param name:
        @return:
        """
        self.ui_click(btn, stop=self.I_WQ_INVITE_ENSURE, interval=2.5)

        # 选人
        self.O_WQ_INVITE_COLUMN_1.keyword = name
        self.O_WQ_INVITE_COLUMN_2.keyword = name

        find = False
        for i in range(2):
            self.wait_until_appear(self.I_WQ_INVITE_FRIEND_LIST_APPEAR, wait_time=4)
            self.screenshot()
            in_col_1 = self.ocr_appear_click(self.O_WQ_INVITE_COLUMN_1)
            in_col_2 = self.ocr_appear_click(self.O_WQ_INVITE_COLUMN_2)
            find = in_col_2 or in_col_1
            if find:
                self.wait_until_appear(self.I_WQ_INVITE_SELECTED, wait_time=2)
                self.screenshot()
                if self.appear(self.I_WQ_INVITE_SELECTED):
                    logger.info("friend found and selected")
                    break
                # TODO OCR识别到文字 但是没有选中 尝试重新选择  (选择好友时,弹出协作邀请导致选择好友失败)
            # 检测跨服好友按钮是否高亮
            while 1:
                self.screenshot()
                if not self.appear_highlight(self.I_WQ_INVITE_DIFF_SVR_HIGHLIGHT):
                    self.click(self.I_WQ_INVITE_DIFF_SVR)
                    continue
                break
            # 等待好友列表加载
            self.wait_until_appear(self.I_WQ_INVITE_DIFF_SVR_HIGHLIGHT, wait_time=4)
        # 没有找到需要邀请的人,点击取消 返回悬赏封印界面
        if not find:
            self.screenshot()
            self.ui_click_until_disappear(self.I_WQ_INVITE_CANCEL, interval=1.5)
            return False
        #
        self.ui_click_until_disappear(self.I_WQ_INVITE_ENSURE, interval=1)
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
        logger.info(f"get cooperation size {len(retList)}")
        return retList

    # 使用平均亮度检测是否一致
    def appear_highlight(self, rule_image: RuleImage):
        def compute_region_brightness(img, top_left, width, height):
            """
            计算目标区域的平均亮度 (灰度图的平均值)
            :param img: 目标图像
            :param top_left: 匹配区域的左上角坐标
            :param width: 模板宽度
            :param height: 模板高度
            :return: 区域亮度均值
            """
            # 裁剪出匹配区域
            region = img[top_left[1]:top_left[1] + height, top_left[0]:top_left[0] + width]
            # 转为灰度图
            gray_region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            # 计算灰度均值
            return gray_region.mean()

        src = rule_image.corp(self.device.image)
        template = rule_image.image
        result = cv2.matchTemplate(src, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        brightness_src = compute_region_brightness(src, max_loc, template.shape[1], template.shape[0])
        brightness_template = compute_region_brightness(template, (0, 0), template.shape[1], template.shape[0])

        if max_val > rule_image.threshold and (brightness_src >= brightness_template * rule_image.threshold) and (
                brightness_src <= brightness_template * (2 - rule_image.threshold)):
            rule_image.roi_front[0] = max_loc[0] + rule_image.roi_back[0]
            rule_image.roi_front[1] = max_loc[1] + rule_image.roi_back[1]
            return True
        return False

    @cached_property
    def special_main(self) -> bool:
        # 特殊的庭院需要点一下，左边然后才能找到图标
        main_type = self.config.global_game.costume_config.costume_main_type
        if main_type == MainType.COSTUME_MAIN_3:
            return True
        return False

    def get_config(self):
        return self.config.wanted_quests.wanted_quests_config

    def need_invite_vip(self):
        return bool(self.get_config().invite_friend_name)

    def get_invite_vip_name(self, ctype: CooperationType):
        return self.get_config().invite_friend_name

    def invite_success_callback(self, ctype: CooperationType, name):
        """
           邀请成功回调
        @param ctype:
        @type ctype:
        @param name:
        @type name:
        """

        return True

    def process_ocr(self, txt):
        def detect_spliter(txt):
            index = txt.find('/')
            if index != -1:
                return index
            # 由于斜杠'/'经常被误识别为'7',且悬赏封印悬赏怪物总数没有与‘7’相关的数字
            reg = re.compile(r'^(\d+)([7/])(\d+)$')
            match = reg.match(txt)
            if match:
                return match.start(2)
            return -1

        index = detect_spliter(txt)
        if index < 0:
            return 0, 0, 0
        return int(txt[:index]), 1, int(txt[index + 1:])

    def txt_ocr_appear(self, ocr_item: RuleOcr, reg, img):
        res = ocr_item.ocr(img)
        regex = re.compile(reg)
        ismatch = regex.match(res)
        return ismatch is not None

    def find_wq(self, img):
        def calc_xywh(box):
            rec_x, rec_y, rec_w, rec_h = box[0, 0], box[0, 1], box[1, 0] - box[0, 0], box[2, 1] - box[0, 1]
            x = rec_x + self.O_WQ_TEXT_ALL.roi[0]
            y = rec_y + self.O_WQ_TEXT_ALL.roi[1]
            w = rec_w
            h = rec_h
            return [x, y, w, h]

        res_list = self.O_WQ_TEXT_ALL.detect_and_ocr(img)
        import re
        reg_time = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5]?[0-9]):?([0-5]?[0-9])?$')
        reg_fengyin = re.compile(r'.*[封|野]印.*')
        # 由于斜杠'/'经常被误识别为'7',且悬赏封印悬赏怪物总数没有与‘7’相关的数字
        reg_progress = re.compile(r'^(\d+)([7/])(\d+)$')
        # 没有检测到斜杠，符合格式：前N位与后N位相同,表示已完成
        reg_XX = re.compile(r'^(\d+)\1$')
        for index, res in enumerate(res_list):
            if reg_fengyin.match(res.ocr_text):
                continue
            if reg_time.match(res.ocr_text):
                continue
            if (match := reg_progress.match(res.ocr_text)):
                spliter_index = match.start(2)
                xywh = calc_xywh(res.box)
                self.O_WQ_TEXT_ALL.area = xywh
                cu, re, total = int(res.ocr_text[:spliter_index]), 1, int(res.ocr_text[spliter_index + 1:])
                # 识别结果规范性检查
                if total > 14:
                    logger.warning("Total number of wanted quests is greater than 14")
                    total = total % 10
                if cu > total:
                    logger.warning('Current number of wanted quests is greater than total number')
                    cu = cu % 10
                if cu == total:
                    # 该任务已完成，一般是悬赏任务，邀请人没有做导致的
                    continue
                return cu, re, total, xywh
            # 例如：1414 66 1212
            if reg_XX.match(res.ocr_text):
                continue
            # 什么都没匹配上，判断上一个识别结果如果为悬赏封印，那么认为该识别结果错误，尝试执行一次
            last_index = (index - 1) if index > 0 else 0
            if reg_fengyin.match(res_list[last_index].ocr_text):
                return 0, 1, 3, calc_xywh(res_list[last_index].box)

        return -1, -1, -1, [0, 0, 0, 0]

    def is_wq_remained(self):
        # 检测是否还存在任务
        return self.appear(self.I_WQ_LIST_TOP_BOTTOM_CHECK)



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    import re

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    # import cv2
    #
    # img = cv2.imread(r'E:\2.png')
    # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    #
    # res = t.find_wq(img)

    t.run()
