# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey


from tasks.Restart.config_scheduler import Scheduler
from module.logger import logger
from tasks.Restart.assets import RestartAssets
from tasks.base_task import BaseTask
from module.exception import TaskEnd




class ScriptTask(BaseTask):

    def run(self) -> None:
        raise TaskEnd('ScriptTask end')









