# This Python file uses the following encoding: utf-8
# @author runhey
# 主进程的管理
# github https://github.com/runhey
import asyncio
import sys
import os
import signal
from asyncio.tasks import Task
from threading import Thread

from module.logger import logger
from module.config.config import Config
from module.server.script_process import ScriptProcess, ScriptState
from module.server.config_manager import ConfigManager


class MainManager(ConfigManager):
    # config_cache: Config = None  # 缓存当前切换的配置
    script_process: dict[str: ScriptProcess] = None  # 脚本进程
    push_data_thread: Thread = None  # 数据推送线程
    signal_kill_server: bool = False

    def __init__(self) -> None:
        super().__init__()
        self.script_process: dict[str: ScriptProcess] = {}  # 脚本进程
        self._all_script_files = self.all_script_files()
        for script_name in self._all_script_files:
            self.script_process[script_name] = ScriptProcess(script_name)
        self.push_data_thread = Thread(target=self.start_push_data_thread, daemon=True)
        self.push_data_thread.start()

    # def ensure_config_cache(self, config_name: str, reload: bool = False):
    #     if self.config_cache is None:
    #         if config_name not in self._all_script_files:
    #             logger.warning(f'[{config_name}] script file does not exist')
    #             return None
    #         self.config_cache = Config(config_name)
    #     elif self.config_cache.config_name != config_name:
    #         self.config_cache = Config(config_name)
    #     if reload:
    #         self.config_cache = Config(config_name)
    #     return self.config_cache

    def add_script_file(self, file_name: str):
        # 当你添加了新的脚本文件后，需要添加缓存的列表
        if file_name in self._all_script_files:
            logger.warning(f'[{file_name}] script file already exists')
            return
        self._all_script_files = self.all_script_files()
        self.script_process[file_name] = ScriptProcess(file_name)

    def start_push_data_thread(self):
        try:
            asyncio.run(self.push_data_handle())
        except SystemExit as e:
            logger.info('Kill the main process')
            # sys.exit(0)
            try:
                os.kill(os.getpid(), signal.SIGILL)
                print("Process killed successfully.")
            except OSError:
                print("Failed to kill the process.")

        except Exception as e:
            logger.exception(e)
            sys.exit(0)

    async def push_data_handle(self):
        tasks: dict[str, Task] = {}
        from asyncio import sleep
        while 1:
            await sleep(3)
            if MainManager.signal_kill_server:  # 结束所有的进程
                logger.info('Kill all server')
                for script_p in self.script_process.values():
                    await script_p.stop()
                logger.info('Kill push data thread')
                sys.exit(0)
            # logger.info(asyncio.all_tasks())
            for name, script_p in self.script_process.items():
                # 遍历所有的
                # 如果 这个进程未激活 跳过
                # 如果 已经存在了 对应的协程 跳过
                # 如果这个进程异常/运行中 那这个协程也应该存在
                # logger.info(f'检测脚本的process: {name}')
                if script_p.state == ScriptState.INACTIVE:
                    continue
                coroutine_state_name = f'coroutine_state_{name}'
                if coroutine_state_name not in tasks:
                    tasks[coroutine_state_name] = asyncio.create_task(script_p.coroutine_broadcast_state(),
                                                                      name=coroutine_state_name)
                coroutine_log_name = f'coroutine_log_{name}'
                if coroutine_log_name not in tasks:
                    tasks[coroutine_log_name] = asyncio.create_task(script_p.coroutine_broadcast_log(),
                                                                    name=coroutine_log_name)

    @staticmethod
    def config_cache(name: str) -> Config:
        return Config(name)

