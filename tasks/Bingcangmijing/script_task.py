# This Python file uses the following encoding: utf-8
# 兵藏秘境
# @author YLXJ
# github https://github.com/yiliangxiajiao
from datetime import datetime, timedelta
import re
import difflib
from collections import OrderedDict

from module.logger import logger
from module.exception import TaskEnd

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_shikigami_records, page_bingcangmijing
from tasks.Bingcangmijing.assets import BingcangmijingAssets
from tasks.Bingcangmijing.config import Bingcangmijing


def remove_punctuation(text):
    return re.sub(r"[^\w\s]", "", text)


def get_next_monday():
    today = datetime.now()
    # 计算到下一个星期一的天数
    days_ahead = 7 - today.weekday()  # Monday is 0
    next_monday = today + timedelta(days=days_ahead)
    return next_monday.replace(hour=0, minute=0, second=0, microsecond=0)


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, BingcangmijingAssets):
    def run(self):
        con: Bingcangmijing = self.config.bingcangmijing
        self.parse_buff_priority(con)
        self.limit_count = con.bingcangmijing_config.limit_count
        limit_time = con.bingcangmijing_config.limit_time
        self.limit_time: timedelta = timedelta(
            hours=limit_time.hour, minutes=limit_time.minute, seconds=limit_time.second
        )
        self.screenshot()
        self.ui_get_current_page()
        # 切换御魂
        if con.switch_soul_config.enable:
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(con.switch_soul_config.switch_group_team)
        if con.switch_soul_config.enable_switch_by_name:
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(con.switch_soul_config.group_name, con.switch_soul_config.team_name)
        # 前往兵藏秘境界面
        self.ui_goto(page_bingcangmijing)
        # 按照配置锁定队伍
        self.check_lock(
            con.general_battle_config.lock_team_enable,
            self.I_BCMJ_LOCK,
            self.I_BCMJ_UNLOCK,
        )
        # 开始循环
        success = True
        no_ticket = False
        while 1:
            self.screenshot()
            while not self.ui_page_appear(page_bingcangmijing):
                self.screenshot()
            normal_ticket_count, _, _ = self.O_BINGDAOTIE_COUNT.ocr(self.device.image)
            if normal_ticket_count == 0:
                vip_ticket_count = self.O_BINGDAOTIE_JIMI_COUNT.ocr(self.device.image)
                if vip_ticket_count == 0:
                    logger.info("No ticket remained")
                    no_ticket = True
                    break
            # 是否达到指定时间或次数
            if self.current_count >= self.limit_count:
                logger.info("Bingcangmijing count limit out")
                break
            if datetime.now() - self.start_time >= self.limit_time:
                logger.info("Bingcangmijing time limit out")
                break
            # 点击挑战
            while True:
                self.screenshot()
                # 每周都会弹一个「开始挑战后不可更换技能和祝福」的提示，点掉他
                self.appear_then_click(self.I_BCMJ_WEEKLY_CONFIRM)
                # 如果需要重置则点击
                self.appear_then_click(self.I_BCMJ_RESET_CONFIRM)
                if not self.appear(self.I_BCMJ_FIRE):
                    break
                self.click(self.I_BCMJ_FIRE)
            # 等待战斗结束
            if self.run_general_battle(config=con.general_battle_config):
                logger.info("Battle success")
            else:
                # 战斗失败退出
                logger.error("Battle failed, turn off task")
                success = False
                break
            # 判断是否需要选择祝福
            while True:
                if self.wait_until_appear(self.I_BCMJ_BUFF_CONFIRM, wait_time=3):
                    logger.info("Prepare to select buff")
                    self.select_buff()
                    break
                else:
                    if self.ui_page_appear(page_bingcangmijing):
                        logger.info("No buff to select")
                        break
        if no_ticket and con.bingcangmijing_config.auto_next_week:
            # 设定下次执行时间为下周一00:00
            next_run_datetime = get_next_monday()
            self.set_next_run(task="Bingcangmijing", target=next_run_datetime)
        else:
            self.set_next_run(task="Bingcangmijing", success=success, finish=True)
        raise TaskEnd

    def parse_buff_priority(self, con: Bingcangmijing):
        def merge_and_deduplicate(custom_priority, default_priority):
            combined = custom_priority + default_priority
            return list(OrderedDict.fromkeys(combined))

        default_priority_list = [
            "天下布武绝命",
            "天下布武刃降",
            "天下布武血怒",
            "鬼神之策刃破",
            "鬼神之策爆烈",
            "鬼神之策剑势",
            "八华斩血啸",
            "八华斩追斩",
            "八华斩增进",
            "血之契追袭",
            "血之契刃反",
            "血之契锐利",
            "天剑退敌",
            "天剑连破",
            "天剑协战",
            "无畏附魂",
            "无畏透甲",
            "鬼胄追击",
            "鬼胄诱敌",
            "剑之垒万刃",
            "剑之垒乘胜",
            "暴击伤害加成",
            "伤害加成",
            "速度提升",
            "暴击加成",
        ]
        custom_priority_str = con.bingcangmijing_config.custom_buff_priority
        custom_priority_list = [
            remove_punctuation(p) for p in custom_priority_str.split(">")
        ]
        self.priority_list = merge_and_deduplicate(
            custom_priority_list, default_priority_list
        )

    def match_buff(self, buff_text):
        best_match = difflib.get_close_matches(buff_text, self.priority_list, n=1)
        if best_match:
            return self.priority_list.index(best_match[0])
        return None

    def select_buff(self):
        buff_texts = []
        buff_texts.append(remove_punctuation(self.O_BUFF_1.ocr(self.device.image)))
        buff_texts.append(remove_punctuation(self.O_BUFF_2.ocr(self.device.image)))
        buff_texts.append(remove_punctuation(self.O_BUFF_3.ocr(self.device.image)))
        buff_texts.append(remove_punctuation(self.O_BUFF_4.ocr(self.device.image)))
        # 找出最佳buff
        best_buff = ""
        best_buff_i = 0
        best_index = 99999
        for i, bt in enumerate(buff_texts):
            index = self.match_buff(bt)
            if index is not None:
                if index < best_index:
                    best_index = index
                    best_buff_i = i + 1
                    best_buff = bt
        logger.info(f"Select buff {best_buff_i}: {best_buff}")
        # 选择
        if best_buff_i == 1:
            self.ui_click_until_disappear(self.I_BCMJ_BUFF1_CLICK)
        elif best_buff_i == 2:
            self.ui_click_until_disappear(self.I_BCMJ_BUFF2_CLICK)
        elif best_buff_i == 3:
            self.ui_click_until_disappear(self.I_BCMJ_BUFF3_CLICK)
        elif best_buff_i == 4:
            self.ui_click_until_disappear(self.I_BCMJ_BUFF4_CLICK)
        else:
            logger.warning("No matched buff, select buff 1 by default")
            self.ui_click_until_disappear(self.I_BCMJ_BUFF1_CLICK)
        self.ui_click_until_disappear(self.I_BCMJ_BUFF_CONFIRM)

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        # 重写
        # 有的时候是长战斗，需要在设置stuck检测为长战斗
        # 但是无需取消设置，因为如果有点击或者滑动的话 handle_control_check会自行取消掉
        self.device.stuck_record_add("BATTLE_STATUS_S")
        self.device.click_record_clear()
        logger.info("Start battle process")
        win: bool = False
        while 1:
            self.screenshot()
            # 胜利
            if self.appear(self.I_WIN, threshold=0.8):
                logger.info("Battle result is win")
                win = True
                break

            # 失败
            if self.appear(self.I_FALSE, threshold=0.8):
                logger.info("Battle result is false")
                win = False
                break

            # 如果开启战斗过程随机滑动
            if random_click_swipt_enable:
                self.random_click_swipt()

        # 再次确认战斗结果
        logger.info("Reconfirm the results of the battle")
        while 1:
            self.screenshot()
            if win:
                # 点击赢了
                if self.appear_then_click(
                    self.I_WIN, action=self.C_WIN_1, interval=0.5
                ):
                    continue
                if not self.appear(self.I_WIN):
                    break
            else:
                # 如果失败且 点击失败后
                if self.appear_then_click(self.I_FALSE, threshold=0.6):
                    continue
                if not self.appear(self.I_FALSE, threshold=0.6):
                    return False

        return win


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    c = Config("oas2")
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
