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


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, BingcangmijingAssets):
    def run(self):
        con: Bingcangmijing = self.config.bingcangmijing
        self.parse_buff_priority(con)
        self.limit_count = con.bingcangmijing_config.limit_count
        limit_time = con.bingcangmijing_config.limit_time
        self.limit_time: timedelta = timedelta(
            hours=limit_time.hour, minutes=limit_time.minute, seconds=limit_time.second
        )
        # 切换御魂
        if con.switch_soul_config.enable:
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(con.switch_soul_config.switch_group_team)
        # 前往兵藏秘境界面
        self.ui_goto(page_bingcangmijing)
        # 按照配置锁定队伍
        self.check_lock(
            con.general_battle_config.lock_team_enable,
            self.I_BCMJ_LOCK,
            self.I_BCMJ_UNLOCK,
        )
        # 开始循环
        while 1:
            self.screenshot()
            while not self.ui_page_appear(page_bingcangmijing):
                self.screenshot()
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
                # 重置
                self.appear_then_click(self.I_BCMJ_RESET_CONFIRM)
                if not self.appear(self.I_BCMJ_FIRE):
                    break
                self.click(self.I_BCMJ_FIRE)
            # 等待战斗结束
            if self.run_general_battle(config=con.general_battle_config):
                logger.info("Battle success")
            else:
                # 如果失败关闭任务
                logger.error("Battle failed, turn off task")
                self.config.close_task("Bingcangmijing")
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

        self.set_next_run(task="Bingcangmijing", success=True, finish=True)
        raise TaskEnd
    
    def remove_punctuation(text):
        return re.sub(r'[^\w\s]', '', text)
        
    def parse_buff_priority(self, con: Bingcangmijing):
        def merge_and_deduplicate(custom_priority, default_priority):
            combined = custom_priority + default_priority
            return list(OrderedDict.fromkeys(combined))
        default_priority_list = [
            "天下布武绝命","天下布武刃降","天下布武血怒",
            "鬼神之策刃破","鬼神之策爆烈","鬼神之策剑势",
            "八华斩血啸","八华斩追斩","八华斩增进",
            "血之契追袭","血之契刃反","血之契锐利",
            "天剑退敌","天剑连破","天剑协战",
            "无畏附魂","无畏透甲",
            "鬼胄追击","鬼胄诱敌",
            "剑之垒万刃","剑之垒乘胜",
            "暴击伤害加成","伤害加成","速度提升","暴击加成",
        ]
        custom_priority_str = con.bingcangmijing_config.custom_buff_priority
        custom_priority_list = [ScriptTask.remove_punctuation(p) for p in custom_priority_str.split(">")]
        self.priority_list = merge_and_deduplicate(custom_priority_list, default_priority_list)

    def match_buff(self, buff_text):
        best_match = difflib.get_close_matches(buff_text, self.priority_list, n=1)
        if best_match:
            return self.priority_list.index(best_match[0])
        return None

    def select_buff(self):
        buff_texts = []
        buff_texts.append(ScriptTask.remove_punctuation(self.O_BUFF_1.ocr(self.device.image)))
        buff_texts.append(ScriptTask.remove_punctuation(self.O_BUFF_2.ocr(self.device.image)))
        buff_texts.append(ScriptTask.remove_punctuation(self.O_BUFF_3.ocr(self.device.image)))
        buff_texts.append(ScriptTask.remove_punctuation(self.O_BUFF_4.ocr(self.device.image)))
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


if __name__ == "__main__":
    from module.config.config import Config
    from module.device.device import Device

    c = Config("oas1")
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
