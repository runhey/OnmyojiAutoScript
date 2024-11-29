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
        self.device.stuck_record_add('LOGIN_CHECK')

        confirm_timer = Timer(1.5, count=2).start()
        orientation_timer = Timer(3)
        login_success = False
        self.mail_count = 0

        while 1:
            # Watch device rotation
            if not login_success and orientation_timer.reached():
                # Screen may rotate after starting an app
                self.device.get_orientation()
                orientation_timer.reset()

            self.screenshot()

            # 确认进入庭院
            if self.appear_then_click(self.I_LOGIN_SCROOLL_CLOSE, interval=2, threshold=0.9):
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


            # 跳过观看视频
            # if self.ocr_appear_click(self.O_LOGIN_SKIP_1, interval=1):
            #     continue
            # 下载插画
            if self.appear_then_click(self.I_LOGIN_LOAD_DOWN, interval=1):
                logger.info('Download inbetweening')
                continue
            # 不观看视频
            if self.appear_then_click(self.I_WATCH_VIDEO_CANCEL, interval=0.6):
                logger.info('Close video')
                continue
            # 右上角的红色的关闭
            if self.appear_then_click(self.I_LOGIN_RED_CLOSE, interval=0.6):
                logger.info('Close red close')
                continue
            # 左上角的黄色关闭
            if self.appear_then_click(self.I_LOGIN_YELLOW_CLOSE, interval=0.6):
                logger.info('Close yellow close')
                continue
            # 点击屏幕进入游戏
            if self.appear(self.I_LOGIN_SPECIFIC_SERVE, interval=0.6) and self.ocr_appear_click(self.O_LOGIN_SPECIFIC_SERVE, interval=0.6):
                logger.info('login specific user')
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
        logger.critical('Onmyoji server may be under maintenance, or you may lost network connection')
        raise RequestHumanTakeover



    def harvest(self):
        """
        获得奖励
        :return: 如果没有发现任何奖励后退出
        """
        logger.hr('Harvest')
        timer_harvest = Timer(13)  # 如果连续3秒没有发现任何奖励，退出
        while 1:
            self.screenshot()

            # 点击'获得奖励'
            if self.ui_reward_appear_click():
                timer_harvest.reset()
                continue
            # 获得奖励
            if self.appear_then_click(self.I_UI_AWARD, interval=0.2):
                timer_harvest.reset()
                continue
            # 偶尔会打开到聊天频道
            if self.appear_then_click(self.I_HARVEST_CHAT_CLOSE, interval=1):
                timer_harvest.reset()
                continue

            # 勾玉
            if self.appear_then_click(self.I_HARVEST_JADE, interval=1.5):
                timer_harvest.reset()
                continue
            # 签到
            if self.appear_then_click(self.I_HARVEST_SIGN, interval=1.5):
                timer_harvest.reset()
                continue
            # 某些活动的特殊签到，有空看到就删掉
            if self.appear_then_click(self.I_HARVEST_SIGN_3, interval=0.7):
                continue
            if self.appear_then_click(self.I_HARVEST_SIGN_4, interval=1):
                timer_harvest.reset()
                continue
            if self.appear_then_click(self.I_HARVEST_SIGN_2, interval=1.5):
                timer_harvest.reset()
                continue
            # 999天的签到福袋
            if self.appear_then_click(self.I_HARVEST_SIGN_999, interval=1.5):
                timer_harvest.reset()
                continue
            # 邮件
            # 判断是否勾选了收取邮件（不收取邮件可以查看每日收获）
            if self.config.restart.harvest_config.enable_mail and self.mail_count == 0:
                if self.appear_then_click(self.I_HARVEST_MAIL, interval=3):
                    self.mail_count = 1
                    timer_harvest.reset()
                    self.wait_until_appear(self.I_HARVEST_MAIL_TITLE, wait_time=2)
                    if self.appear(self.I_HARVEST_MAIL_TITLE, interval=2.5):
                        while 1:
                            self.screenshot()
                            if self.appear_then_click(self.I_HARVEST_MAIL_ALL, interval=2):
                                timer_harvest.reset()
                                pass
                            if self.appear_then_click(self.I_HARVEST_MAIL_CONFIRM, interval=1):
                                continue

                            # 如果一直出现收取全部，那就说明还在进行中
                            if self.appear(self.I_HARVEST_MAIL_ALL):
                                pass
                            # 如果没有出现 ‘收取全部’ 也没有出现 ‘还未读的邮件’ 那就可以退出了
                            if not self.appear(self.I_HARVEST_MAIL_ALL) and not self.appear(self.I_HARVEST_MAIL_OPEN):
                                logger.info('Mail has been harvested')
                                logger.info('Exit mail')
                                break
                            if self.appear_then_click(self.I_HARVEST_MAIL_OPEN, interval=1):
                                timer_harvest.reset()
                                continue
                        self.appear_then_click(self.I_UI_BACK_RED, interval=2.3)
                        continue
            # 体力
            if self.appear_then_click(self.I_HARVEST_AP, interval=1, threshold=0.7):
                timer_harvest.reset()
                continue
            # 御魂觉醒加成
            if self.appear_then_click(self.I_HARVEST_SOUL, interval=1):
                timer_harvest.reset()
                continue
            # 寮包
            if self.appear_then_click(self.I_HARVEST_GUILD_REWARD, interval=2):
                timer_harvest.reset()
                continue
            # 自选御魂
            if self.appear(self.I_HARVEST_SOUL_1):
                logger.info('Select soul 1')
                self.ui_click(self.I_HARVEST_SOUL_1, stop=self.I_HARVEST_SOUL_2)
                self.ui_click(self.I_HARVEST_SOUL_2, stop=self.I_HARVEST_SOUL_3, interval=3)
                self.ui_click_until_disappear(click=self.I_HARVEST_SOUL_3)
                timer_harvest.reset()


            # 红色的关闭
            if self.appear_then_click(self.I_UI_BACK_RED, interval=2.3):
                timer_harvest.reset()
                continue

            # 三秒内没有发现任何奖励，退出
            if not timer_harvest.started():
                timer_harvest.start()
            else:
                if timer_harvest.reached():
                    logger.info('No more reward')
                    return

