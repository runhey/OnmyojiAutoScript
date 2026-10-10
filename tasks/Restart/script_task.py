# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime

from tasks.Restart.config_scheduler import Scheduler
from tasks.Restart.login import LoginHandler
from tasks.Restart.assets import RestartAssets
from tasks.base_task import BaseTask, Time
from datetime import datetime, time

from module.logger import logger
from module.exception import (TaskEnd,
                              RequestHumanTakeover,
                              GameNotRunningError,
                              GameStuckError,
                              GameTooManyClickError)

# 桌面客户端「启动+登录」的就地重试轮数：Restart 就是负责启动客户端的任务，
# 起不来必须自己扛住，抛给调度器会形成无限重启循环
DESKTOP_RESTART_ATTEMPTS = 3


class ScriptTask(LoginHandler):

    def run(self) -> None:
        """
        主要就是登录的模块
        :return:
        """
        if not self.delay_pending_tasks():
            self.app_restart()
        raise TaskEnd('ScriptTask end')

    def app_stop(self):
        logger.hr('App stop')
        self.device.app_stop()

    def app_start(self):
        logger.hr('App start')
        if self.device.is_desktop:
            self._desktop_start_and_login()
            return
        self.device.app_start()
        self.app_handle_login()
        # self.ensure_no_unfinished_campaign()

    def app_restart(self):
        logger.hr('App restart')
        if self.device.is_desktop:
            # 客户端可能刚被自动拉起（停在登录页），先停再起会白关一次
            self._desktop_start_and_login()
        else:
            self.device.app_stop()
            self.device.app_start()
            self.app_handle_login()

        # self.config.task_delay(server_update=True)
        self.set_next_run(task='Restart', success=True, finish=True, server=True)
        # 如果启用了定时领体力（每天 12-14、20-22 时内各有 20 体力）
        if self.config.restart.harvest_config.enable_ap:
            now = datetime.now()
            # 如果时间在00:00-12:00之间则设定时间为当日 12 时
            if now.time() < time(12, 0):
                self.custom_next_run(task='Restart', custom_time=Time(12, 0), time_delta=0)
            # 如果时间在12:00-20:00之间则设定时间为当日 20 时
            elif now.time() >= time(12, 0) and now.time() < time(20, 0):
                self.custom_next_run(task='Restart', custom_time=Time(20, 0), time_delta=0)
            # 如果时间在20:00-23:59之间则设定时间为次日 12 时
            else:
                self.custom_next_run(task='Restart', custom_time=Time(12, 0), time_delta=1)

    def _desktop_start_and_login(self) -> None:
        """桌面模式：拉起客户端并登录，客户端窗口丢失时就地重拉，不把异常抛给调度器。

        Restart 就是负责启动客户端的任务：GameNotRunningError 抛出去会被 script.py
        接住再 task_call('Restart')，形成无限重启循环（每轮日志都「正常」，比直接崩
        更难排查），所以必须在这里就地消化。登录流程自身的失败重试由 app_handle_login
        内部完成（它会关掉客户端再重拉），这里只补「客户端窗口丢失」这一类重拉。
        """
        for attempt in range(1, DESKTOP_RESTART_ATTEMPTS + 1):
            try:
                self.device.app_start()
                self.app_handle_login()
                return
            except (GameNotRunningError, GameStuckError, GameTooManyClickError) as e:
                logger.warning(f'桌面客户端启动后仍未就绪（第 {attempt}/{DESKTOP_RESTART_ATTEMPTS} 轮）: {e}')
                # 每轮失败都清掉本轮客户端，否则残留窗口会干扰下一轮的新窗口识别
                logger.info('清理本轮残留客户端')
                if not self.device.desktop_stop_client():
                    # 关不掉就别重建：残留窗口会让下一轮绑错句柄，越试越乱
                    logger.critical('桌面客户端无法关闭，残留进程会干扰重建，请手动结束该进程')
                    raise RequestHumanTakeover
        logger.critical(f'桌面客户端连续 {DESKTOP_RESTART_ATTEMPTS} 轮启动失败，请检查客户端与机器状态')
        raise RequestHumanTakeover

    def delay_pending_tasks(self) -> bool:
        """
        周三更新游戏的时候延迟
        @return:
        """
        datetime_now = datetime.now()
        if not (datetime_now.weekday() == 2 and 6 <= datetime_now.hour <= 8):
            return False
        logger.info("The game server is updating, delay the pending tasks to 9:00")
        logger.warning('Delay pending tasks')
        # running 中的必然是 Restart
        for task in self.config.pending_task:
            print(task.command)
            self.set_next_run(task=task.command, target=datetime_now.replace(hour=9, minute=0, second=0, microsecond=0))
        self.set_next_run(task='Restart', success=True, finish=True, server=True)
        return True


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    config = Config('oas1')
    device = Device(config)
    task = ScriptTask(config, device)
    for i in range(3):
        task.app_restart()
    # task.config.update_scheduler()
    # task.delay_pending_tasks()









