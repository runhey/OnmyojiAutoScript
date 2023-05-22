# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from multiprocessing import Process

from module.logger import logger


class ScriptProcess(Process):

    def __init__(self, config: str) -> None:
        """

        :param config: 如oas1
        """
        super().__init__()
        self.config = config
        self.name = config
        self.daemon = True  # 设置为守护进程，主进程结束，子进程也结束

    @property
    def alive(self) -> bool:
        """
        alive
        :return:
        """
        return self.is_alive()

    def run(self) -> None:
        """
        run
        :return:
        """
        try:
            from script import Script
            script = Script(config_name=self.config)
        except:
            logger.exception(f'run script {self.config} error')
            raise

    def stop(self) -> None:
        """
        stop the  process
        是强制的，不会等待子进程结束
        :return:
        """
        self.terminate()
        self.join()
        logger.info(f'stop script {self.config}')

    def restart(self) -> None:
        """
        restart the process
        :return:
        """
        self.stop()
        self.start()
        logger.info(f'restart script {self.config}')
