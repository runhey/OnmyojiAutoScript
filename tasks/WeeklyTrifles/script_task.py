# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
from time import sleep

from module.exception import TaskEnd
from module.logger import logger
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_collection, page_area_boss, page_secret_zones, page_summon, random_click
from tasks.WeeklyTrifles.config import Trifles
from tasks.WeeklyTrifles.assets import WeeklyTriflesAssets

class ScriptTask(GameUi, WeeklyTriflesAssets):

    def run(self):
        con = self.config.weekly_trifles.trifles
        if con.share_collect:
            self._share_collect()
        if con.share_area_boss:
            self._share_area_boss()
        if con.share_secret:
            self._share_secret()
        if con.broken_amulet:
            self._broken_amulet(con.broken_amulet)

        self.set_next_run(task='WeeklyTrifles', success=True, finish=True)
        raise TaskEnd('WeeklyTrifles')


    def click_share(self, wechat) -> bool:
        """
        点击分享
        :param wechat:
        :return:
        """
        # 点击分享
        # self.ui_click(wechat, self.I_WT_QR_CODE)
        while 1:
            self.screenshot()
            if self.appear(self.I_WT_QR_CODE):
                break
            if self.appear_then_click(wechat, interval=2.5):
                continue
        logger.info('Click share')
        get_timer = Timer(7)
        get_timer.start()
        while 1:
            self.screenshot()
            if self.ui_reward_appear_click():
                logger.info('Get reward')
                return True
            if self.appear_then_click(self.I_WT_QR_CODE, self.C_WT_WECHAT, interval=4.8):
                continue
            if get_timer.reached():
                logger.warning('Share timeout. The reward may have been obtained')
                return False

    def _share_collect(self):
        """
        图鉴分享
        :return:
        """
        logger.hr('Share collect')
        self.ui_get_current_page()
        self.ui_goto(page_collection)
        # 一路进去
        while 1:
            self.screenshot()
            if self.appear(self.I_WT_COLLECT):
                break
            if self.appear_then_click(self.I_WT_SHIKIAGMI, interval=1):
                continue
            if self.appear_then_click(self.I_WT_SCROLL, interval=1):
                continue
        # 确认的是百鬼夜行图
        self.ui_click(self.I_WT_SCROLL_2, self.I_WT_SCROLL_1)
        logger.info('Confirm the picture is 百妖风物鉴')
        # 点击分享
        while 1:
            self.screenshot()
            if self.appear(self.I_WT_QR_CODE):
                break
            if self.appear_then_click(self.I_WT_COLLECT_WECHAT, interval=1):
                continue
            if self.appear_then_click(self.I_WT_COLLECT, interval=5):
                continue
        logger.info('Click share')
        get_timer = Timer(3)
        get_timer.start()
        while 1:
            self.screenshot()

            if self.ui_reward_appear_click():
                logger.info('Get reward')
                break

            if self.appear_then_click(self.I_WT_QR_CODE, self.C_WT_WECHAT, interval=0.8):
                continue
            if get_timer.reached():
                logger.warning('Share timeout. The reward may have been obtained')
                break
        # 返回
        while 1:
            self.screenshot()
            if self.appear(self.I_WT_SHIKIAGMI):
                break
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1):
                continue
            if self.appear_then_click(self.I_UI_BACK_BLUE, interval=1):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1):
                continue

    def _share_area_boss(self):
        """
        地鬼分享
        :return:
        """
        def back_boss():
            while 1:
                self.screenshot()
                if self.appear(self.I_WT_DAY_BATTLE) or self.appear(self.I_CHECK_EXPLORATION):
                    break
                if self.appear_then_click(self.I_UI_BACK_RED, interval=1):
                    continue
                if self.appear_then_click(self.I_UI_BACK_BLUE, interval=1):
                    continue
                if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1):
                    continue
            logger.info('Back to boss')
        logger.hr('Share area boss')
        self.ui_get_current_page()
        self.ui_goto(page_area_boss)

        # 一路进去
        obtained = False
        while 1:
            self.screenshot()
            if self.appear(self.I_WT_AB_WECHAT):
                break
            if self.appear(self.I_WT_NO_DAY):
                obtained = True
                break
            if self.click(self.C_WT_AB_CLICK, interval=1):
                continue
            if self.appear_then_click(self.I_WT_DAY_BATTLE, interval=2):
                continue
            if self.appear_then_click(self.I_WT_SHARE_AB, interval=1):
                continue
        # 再次检查一次这周有没有领取
        time.sleep(1)
        self.screenshot()
        if not self.appear(self.I_WT_AB_JADE):
            logger.warning('This week has been obtained')
            obtained = True
        if not obtained:
            # 点击分享
            self.click_share(self.I_WT_AB_WECHAT)
            obtained = True
        if obtained:
            back_boss()

    def _share_secret(self):
        """
        秘闻分享
        :return:
        """
        logger.hr('Share secret')
        self.ui_get_current_page()
        self.ui_goto(page_secret_zones)
        # 一路进去
        valid = False
        while 1:
            self.screenshot()
            if self.appear(self.I_WT_SE_WECHAT):
                self.wait_until_stable(self.I_WT_SE_WECHAT, skip_first_screenshot=True)
                break
            if self.appear_then_click(self.I_WT_ENTER_SE, interval=1):
                continue
            if self.appear_then_click(self.I_WT_SE_SHARE, interval=5):
                valid = True
                continue
            if self.appear(self.I_WT_SE_RANK) and (not valid):
                # 如果出现排名但是没有出现分享，那就是还没打，退出
                self.wait_until_stable(self.I_WT_SE_SHARE, skip_first_screenshot=True)
                if self.appear(self.I_WT_SE_SHARE):
                    continue
                logger.warning('This week has not been obtained')
                self.ui_click(self.I_UI_BACK_BLUE, self.I_CHECK_MAIN)
                return
        logger.info('Enter secret')
        # 判断是否已经领取
        self.screenshot()
        obtained = False
        if not self.appear(self.I_WT_SE_JADE):
            obtained = True
            logger.warning('This week has been obtained')
        # 点击分享
        if not obtained:
            self.click_share(self.I_WT_SE_WECHAT)
        # 返回
        self.ui_click(self.I_UI_BACK_BLUE, self.I_CHECK_MAIN)

    def _broken_amulet(self, dest_num: int):
        """

        :param dest_num:
        :return:
        """
        def exit_amulet():
            self.wait_until_appear(self.I_BM_CONFIRM, wait_time=3)
            while 1:
                self.screenshot()
                if not self.appear(self.I_BM_CONFIRM):
                    break
                else:
                    self.appear_then_click(self.I_BM_CONFIRM, interval=1)
            logger.info('Exit broken amulet')

        logger.hr('Broken amulet')
        self.ui_get_current_page()
        self.ui_goto(page_summon)
        self.screenshot()
        real_num = self.O_BA_AMOUNT_1.ocr(self.device.image)
        if real_num <= 0:
            logger.warning('No broken amulet')
            return
        logger.info(f'Broken amulet: {real_num}')
        count = 0
        self.wait_until_appear(self.I_BM_ENTER)
        logger.info('Enter broken amulet')
        while count < dest_num:
            self.screenshot()
            real_num = self.O_BA_AMOUNT_1.ocr(self.device.image)
            if real_num <= 0:
                exit_amulet()
                return
            if self.appear_then_click(self.I_BM_ENTER, interval=1) or self.appear_then_click(self.I_BM_AGAIN, interval=1):
                sleep(0.4)  # 等待动画开始
                timeout_timer = Timer(5).start()
                # 随机点击直到再次召唤出现或者超时
                while not timeout_timer.reached():
                    if not self.click(random_click(), interval=0.8):
                        continue
                    self.screenshot()
                    if self.appear(self.I_BM_AGAIN, interval=0.8):
                        break
                else:
                    logger.warning(f'Wait for again timeout:Count[{count}], Remain[{real_num}]')
                    exit_amulet()
                    return
            else:
                # 既没有出现召唤破碎符咒也没有出现再次召唤, 则退出(一般不会出现这种情况, 只是为了异常处理)
                exit_amulet()
                return
            x_10, _, _, _ = self.O_BA_TIMES.ocr(self.device.image, '10次')
            x_50, _, _, _ = self.O_BA_TIMES.ocr(self.device.image, '50次')
            self.I_BMT_CHECK.match(self.device.image)
            x_check, y_check, width_check, height_check = self.I_BMT_CHECK.roi_front
            selected_10 = min(abs(x_10 - x_check), abs(x_50 - x_check)) == abs(x_10 - x_check)
            logger.info(f'Current selected {"10" if selected_10 else "50"} amulet')
            count += 10 if selected_10 else 50
            logger.info(f'Broken amulet:Count[{count}], Remain[{real_num}]')
            # 一次50票不超过限制且当前选择的是10票则切换50票
            if count + 50 < dest_num and selected_10:
                logger.hr('Switch to 50 amulet')
                self.device.click(x=x_50 - width_check // 2, y=y_check + height_check // 2, control_name='Click_50')
                self.device.click_record_clear()
            # 一次50票会超过限制且当前选择的是50票则切换10票
            if count + 50 >= dest_num and not selected_10:
                logger.hr('Switch to 10 amulet')
                self.device.click(x=x_10 - width_check // 2, y=y_check + height_check // 2, control_name='Click_10')
                self.device.click_record_clear()
        # 正常结束且还有票, 则执行一次退出
        exit_amulet()


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    # t._share_secret()
    t._share_area_boss()
    # t.click_share(t.I_WT_SE_WECHAT)


