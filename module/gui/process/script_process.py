# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from queue import Queue
from multiprocessing import Process

from module.logger import logger


class ScriptProcess(Process):

    def __init__(self, config: str, port: int, log_queue: Queue, update_queue: Queue) -> None:
        """

        :param port: 端口 tcp 127.0.0.1:port
        :param config: 如oas1
        :param log_queue: 一个输出到gui的Log队列
        """
        super().__init__()
        self.config = config
        self.port = port
        self.name = config
        self.log_queue = log_queue
        self.update_queue = update_queue
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
        self.start_log()
        try:
            from script import Script
            script = Script(config_name=self.config)
            script.gui_update_task = self.update_tasks
            script.init_server(self.port)
            script.run_server()
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

    # def restart(self) -> None:
    #     """
    #     restart the process
    #     :return:
    #     """
    #     super().restart()
    #     logger.info(f'restart script {self.config}')

    def start_log(self) -> None:
        """

        :return:
        """
        try:
            from module.logger import set_file_logger, set_func_logger
            set_file_logger(name=self.config)
            set_func_logger(self.log_queue.put)
        except:
            logger.exception(f'start log error')
            raise


    def update_tasks(self, data) -> None:
        """
        update tasks
        :return:
        """
        msg = {self.config: data}
        self.update_queue.put(msg)
        logger.info(f'Update tasks {self.config}')

