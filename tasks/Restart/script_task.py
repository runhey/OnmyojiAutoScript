# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime

from tasks.Restart.config_scheduler import Scheduler
from tasks.Restart.login import LoginHandler
from tasks.Restart.assets import RestartAssets
from tasks.base_task import BaseTask

from module.logger import logger
from module.exception import TaskEnd, RequestHumanTakeover


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
        self.device.app_start()
        self.app_handle_login()
        # self.ensure_no_unfinished_campaign()

    def app_restart(self):
        logger.hr('App restart')
        self.device.app_stop()
        self.device.app_start()
        self.app_handle_login()

        # self.config.task_delay(server_update=True)
        self.set_next_run(task='Restart', success=True, finish=True, server=True)

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
    task.config.update_scheduler()
    task.delay_pending_tasks()
    # task.screenshot()
    # print(task.appear_then_click(task.I_LOGIN_SCROOLL_CLOSE, threshold=0.9))








