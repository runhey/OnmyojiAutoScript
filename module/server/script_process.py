# This Python file uses the following encoding: utf-8
# @author runhey
# 脚本进程
# github https://github.com/runhey
import multiprocessing
from asyncio import QueueEmpty, CancelledError, sleep
from enum import Enum

from module.logger import logger

from module.server.script_websocket import ScriptWSManager

class ScriptState(int, Enum):
    INACTIVE = 0
    RUNNING = 1
    WARNING = 2
    UPDATING = 3

class ScriptProcess(ScriptWSManager):

    def __init__(self, config_name: str) -> None:
        super().__init__()
        self.config_name = config_name  # config_name
        self.log_pipe_out, self.log_pipe_in = multiprocessing.Pipe(False)
        self.state_queue = multiprocessing.Queue()
        self.state: ScriptState = ScriptState.INACTIVE
        self._process = None
        self._process = multiprocessing.Process(target=func,
                                                args=(config_name, self.state_queue, self.log_pipe_in,),
                                                name=self.config_name,
                                                daemon=True)




    def start(self):
        if self._process is None:
            logger.warning(f'Script {self.config_name} is not initialized')
            return
        if self._process.is_alive():
            logger.warning(f'Script {self.config_name} is already running and first stop it')
            self.stop()
        self._process.start()
        self.state = ScriptState.RUNNING
        self.state_queue.put({"state": self.state})

    def stop(self):
        if self._process is None:
            logger.warning(f'Script {self.config_name} is not initialized')
            return
        if not self._process.is_alive():
            logger.warning(f'Script {self.config_name} is not running')
            return
        self._process.terminate()
        self.state = ScriptState.INACTIVE
        self.state_queue.put({"state": self.state})




    # def func(self):
    #     # self.start_log(log_pipe_in)
    #     try:
    #         from script import Script
    #         # script = Script(config_name=self.config_name)
    #         # script.state_queue = state_queue
    #         # script.loop()
    #         # 脚本启动
    #         from time import sleep
    #         logger.info(f'Script {self.config_name} start')
    #         sleep(5)
    #         logger.info(f'Script {self.config_name} end')
    #         exit(0)
    #         raise Exception('test')
    #     except SystemExit as e:
    #         logger.info(f'Script {self.config_name} exit')
    #         self.state = ScriptState.WARNING
    #         self.state_queue.put({"state": self.state})
    #     except Exception as e:
    #         logger.exception(f'Run script {self.config_name} error')
    #         logger.error(f'Error: {e}')
    #         raise

    # def start_log(self, log_pipe_in) -> None:
    #     try:
    #         from module.logger import set_file_logger, set_func_logger
    #         set_file_logger(name=self.config_name)
    #         set_func_logger(log_pipe_in.send)
    #     except Exception as e:
    #         logger.exception(f'Start log error')
    #         logger.error(f'Error: {e}')
    #         raise


    async def broadcast_state_log(self):
        try:
            data = self.state_queue.get_nowait()
            if not data:
                pass
            if self.state == ScriptState.INACTIVE:
                pass
            await self.broadcast_state(data)
        except QueueEmpty as e:
            pass
        except Exception as e:
            raise e

    async def coroutine_broadcast_state(self):
        try:
            while 1:
                await sleep(0.1)
                try:
                    data = self.state_queue.get_nowait()
                    if not data:
                        await sleep(0.5)
                        continue
                    if self.state == ScriptState.INACTIVE:
                        logger.warning()
                        continue
                    await self.broadcast_state(data)
                except QueueEmpty as e:
                    await sleep(0.5)
                    continue
                except Exception as e:
                    raise e
        except CancelledError as e:
            logger.warning(f'{self.config_name} state coroutine is cancelled')
            return


def func(config: str, state_queue: multiprocessing.Queue, log_pipe_in) -> None:
    def start_log() -> None:
        try:
            from module.logger import set_file_logger, set_func_logger
            set_file_logger(name=config)
            set_func_logger(log_pipe_in.send)
        except Exception as e:
            logger.exception(f'Start log error')
            logger.error(f'Error: {e}')
            raise
    start_log()
    try:
        from script import Script
        script = Script(config_name=config)
        script.state_queue = state_queue
        script.loop()
        # 脚本启动
        # from time import sleep
        # logger.info(f'Script {self.config_name} start')
        # sleep(5)
        # logger.info(f'Script {self.config_name} end')
        # exit(0)
        # raise Exception('test')
    except SystemExit as e:
        logger.info(f'Script {config} exit')
        state_queue.put({"state": ScriptState.WARNING})
    except Exception as e:
        logger.exception(f'Run script {config} error')
        logger.error(f'Error: {e}')
        raise


if __name__ == '__main__':
    p = ScriptProcess('oas1')
    p.start()
    from time import sleep
    sleep(10)
    logger.info(p._process.exitcode)


