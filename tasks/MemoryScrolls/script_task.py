# This Python file uses the following encoding: utf-8
# @author ghg11
# github https://github.com/ghg11
from time import sleep
from enum import Enum
from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer
from datetime import timedelta, datetime

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_summon
from tasks.MemoryScrolls.assets import MemoryScrollsAssets
from tasks.MemoryScrolls.config import ScrollNumber


class ScriptTask(GameUi, MemoryScrollsAssets):

    def run(self):        
        self.ui_get_current_page()
        self.ui_goto(page_summon)
        con = self.config.memory_scrolls.memory_scrolls_config
        # 进入绘卷主界面
        self.goto_memoryscrolls_main(con) 
        raise TaskEnd
    
    def goto_memoryscrolls_main(self, con):
        # 循环寻找&点击绘卷入口
        if self.wait_until_appear(self.I_MS_ENTER, wait_time=30):
            while 1:
                self.screenshot()
                if self.appear(self.I_MS_FRAGMENT_S):
                    logger.info('Entered Memory Scrolls main page')
                    break
                # 周年庆等时期会使用双绘卷
                if self.appear(self.I_MS_DOUBLE_SCROLLS_ENTER):
                    logger.info('Using Double Memory Scrolls')
                    if con.double_scrolls == con.double_scrolls.ONE:
                        logger.info('Choose Double Memory Scrolls One')
                    else:
                        logger.info('Choose Double Memory Scrolls Two')
                        self.click(self.C_MS_DOUBLE_SCROLLS_2, interval=1)
                    if self.appear_then_click(self.I_MS_DOUBLE_SCROLLS_ENTER, interval=1):
                        continue
                # 右上角绘卷铃铛
                if self.appear_then_click(self.I_MS_ENTER, interval=1):
                    continue
        else:
            logger.error('Failed to enter Memory Scrolls main page')
            self.set_next_run(task='MemoryScrolls', success=False)
            raise TaskEnd
        # 如果每天只刷小绘卷50，则先检测小绘卷数量
        if self.config.memory_scrolls.memory_scrolls_finish.auto_finish_exploration:
            while 1:
                self.screenshot()
                if self.appear(self.I_MS_FRAGMENT_S_VERIFICATION):
                    break
                if self.appear_then_click(self.I_MS_FRAGMENT_S, interval=1.5):
                    continue
            if self.appear(self.I_MS_FRAGMENT_S_50):
                logger.info('Small Memory Scrolls fragments reached 50, planning tomorrow exploration')
                # 安排下次探索
                self.custom_next_run(task='Exploration', custom_time=self.config.memory_scrolls.memory_scrolls_finish.next_exploration_time, time_delta=1)
            self.ui_click_until_smt_disappear(self.I_MS_MAIN, stop=self.I_MS_FRAGMENT_S_VERIFICATION, interval=1.5)
        # 进入指定分卷
        self.goto_scroll(con)
        # 返回召唤界面，目前只发现此种返回按键
        self.ui_click_until_disappear(self.I_MS_BACK, interval=1)
        logger.info('Return to Summon page')
    
    def goto_scroll(self, con):
        """
        进入指定分卷
        :param scroll_number: 分卷编号
        """
        while 1:
            self.screenshot()
            # 暂时用手动截取叉号，后续替换为通用图片
            if self.appear(self.I_MS_CLOSE):
                logger.info('Entered Memory Scrolls contribution page')
                break
            match con.scroll_number:
                case ScrollNumber.ONE:
                    self.click(self.C_MS_SCROLL_1, interval=1)
                case ScrollNumber.TWO:
                    self.click(self.C_MS_SCROLL_2, interval=1)
                case ScrollNumber.THREE:
                    self.click(self.C_MS_SCROLL_3, interval=1)
                case ScrollNumber.FOUR:
                    self.click(self.C_MS_SCROLL_4, interval=1)
                case ScrollNumber.FIVE:
                    self.click(self.C_MS_SCROLL_5, interval=1)
                case ScrollNumber.SIX:
                    self.click(self.C_MS_SCROLL_6, interval=1)
                case _:
                    logger.error(f'Unknown scroll number: {con.scroll_number.name}')
                    self.set_next_run(task='MemoryScrolls', success=False)
                    raise TaskEnd
        
        # 到达指定进度时进行通知提示
        if con.notification_95 and not self.appear(self.I_MS_COMPLETE_95):
            logger.info('Memory Scrolls progress reached 95%, sending notification')
            self.config.notifier.push(title='追忆绘卷进度95%', content='绘卷进度已达95%，请立即空降')

        # 判断是否需要捐献碎片
        if self.appear(self.I_MS_CONTRIBUTE) or not self.appear(self.I_MS_COMPLETE):
            logger.info(f'Contributing Memory Scrolls for scroll {con.scroll_number.name}')
            if con.auto_contribute_memoryscrolls:
                # 自动捐献碎片
                logger.info('Auto contributing Memory Scrolls')
                self.contribute_memoryscrolls()
            # 设置下一次运行时间
            self.set_next_run(task='MemoryScrolls', success=True)
        else:
            logger.info(f'Scroll {con.scroll_number.name} is already completed')
            self.set_next_run(task='MemoryScrolls', success=False)
            if con.auto_close_exploration:
                # 自动关闭探索任务
                logger.info('Auto close exploration task after Memory Scrolls completion')
                self.config.exploration.scheduler.enable = False
                self.config.save()
                # next_run=datetime.now() + timedelta(days=1)
                # self.set_next_run(task='Exploration', success=False, finish=False, target=next_run)
        # 返回绘卷主界面
        self.ui_click_until_disappear(self.I_MS_CLOSE, interval=1)
        logger.info('Closed Memory Scrolls contribution page')
    
    def contribute_memoryscrolls(self):
        """
        捐献碎片
        :return: None
        """
        while 1:
            self.screenshot()
            if self.appear(self.I_MS_ZERO_S) and self.appear(self.I_MS_ZERO_M) and self.appear(self.I_MS_ZERO_L):
                logger.info('Memory Scrolls contribution is already completed')
                return
            self.swipe(self.S_MS_SWIPE_S, interval=1)
            self.swipe(self.S_MS_SWIPE_M, interval=1)
            self.swipe(self.S_MS_SWIPE_L, interval=1)
            if self.appear_then_click(self.I_MS_CONTRIBUTE, interval=3):
                logger.info('Contributed Memory Scrolls')
                # 等待捐献动画结束
                while 1:
                    self.screenshot()
                    if self.wait_until_appear(self.I_MS_CONTRIBUTED, wait_time=5):
                        self.click(self.C_MS_CONTRIBUTED, interval=1)
                    else:
                        break
    



if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()





