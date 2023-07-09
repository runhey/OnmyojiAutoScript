# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from tasks.Restart.config_scheduler import Scheduler
from module.logger import logger
from module.base.timer import Timer

from tasks.Restart.assets import RestartAssets
from tasks.base_task import BaseTask
from module.exception import TaskEnd, RequestHumanTakeover, GameTooManyClickError, GameStuckError


class LoginHandler(BaseTask, RestartAssets):

    def _app_handle_login(self) -> bool:
        """
        最终是在庭院界面
        :return:
        """
        logger.hr('App login')

        confirm_timer = Timer(1.5, count=2).start()
        orientation_timer = Timer(10)
        login_success = False

        while 1:
            # Watch device rotation
            if not login_success and orientation_timer.reached():
                # Screen may rotate after starting an app
                self.device.get_orientation()
                orientation_timer.reset()

            self.screenshot()



            # 确认进入庭院
            if self.appear_then_click(self.I_LOGIN_SCROOLL_CLOSE, interval=2):
                logger.info('Open scroll')
                continue
            if self.appear(self.I_LOGIN_SCROOLL_OPEN, interval=0.2):
                if confirm_timer.reached():
                    logger.info('Login to main confirm')
                    break
            else:
                confirm_timer.reset()
            # 登录成功
            if self.appear(self.I_LOGIN_SCROOLL_OPEN, interval=0.5):
                logger.info('Login success')
                login_success = True

            # 网络异常
            # if self.ocr_appear(self.O_LOGIN_NETWORK):
            #     logger.error('Network error')
            #     raise RequestHumanTakeover('Network error')

            # 右上角的红色的关闭
            if self.appear_then_click(self.I_LOGIN_RED_CLOSE, interval=0.6):
                logger.info('Close red close')
                continue
            # 左上角的黄色关闭
            if self.appear_then_click(self.I_LOGIN_YELLOW_CLOSE, interval=0.6):
                logger.info('Close yellow close')
                continue

            # 点击’进入游戏‘
            if not self.appear(self.I_LOGIN_8):
                continue
            if self.ocr_appear_click(self.O_LOGIN_ENTER_GAME, interval=2.5):
                continue

        return login_success


    def app_handle_login(self) -> bool:
        for _ in range(2):
            self.device.stuck_record_clear()
            self.device.click_record_clear()
            try:
                self._app_handle_login()
                if self.config.restart.harvest_config.enable:
                    self.harvest()
                return True
            except (GameTooManyClickError, GameStuckError) as e:
                logger.warning(e)
                self.device.app_stop()
                self.device.app_start()
                continue

        logger.critical('Login failed more than 3')
        logger.critical('Azur Lane server may be under maintenance, or you may lost network connection')
        raise RequestHumanTakeover



    def harvest(self):
        """
        获得奖励
        :return: 如果没有发现任何奖励后退出
        """
        logger.hr('Harvest')
        timer_harvest = Timer(3)  # 如果连续3秒没有发现任何奖励，退出
        while 1:
            self.screenshot()

            # 点击'获得奖励'
            if self.ui_reward_appear_click():
                continue
            # 获得奖励
            if self.appear_then_click(self.I_UI_AWARD, interval=1):
                continue

            # 勾玉
            if self.appear_then_click(self.I_HARVEST_JADE, interval=1):
                continue
            # 签到
            if self.appear_then_click(self.I_HARVEST_SIGN, interval=1):
                continue
            if self.appear_then_click(self.I_HARVEST_SIGN_2, interval=1):
                continue
            # 999天的签到福袋
            if self.appear_then_click(self.I_HARVEST_SIGN_999, interval=1):
                continue
            # 邮件
            if self.appear_then_click(self.I_HARVEST_MAIL, interval=1):
                continue
            if self.appear_then_click(self.I_HARVEST_MAIL_ALL, interval=1):
                continue
            if self.appear_then_click(self.I_HARVEST_MAIL_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_HARVEST_MAIL_OPEN, interval=1):
                continue


            # 红色的关闭
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1):
                continue

            # 三秒内没有发现任何奖励，退出
            if not timer_harvest.started():
                timer_harvest.start()
            else:
                if timer_harvest.reached():
                    logger.info('No more reward')
                    return

