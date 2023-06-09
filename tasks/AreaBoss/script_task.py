# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time

from tasks.base_task import BaseTask
from module.logger import logger


class ScriptTask(BaseTask):

    def run(self) -> bool:
        """
        运行脚本
        :return:
        """
        time.sleep(10)
        logger.info("运行脚本")
