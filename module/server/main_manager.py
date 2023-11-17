# This Python file uses the following encoding: utf-8
# @author runhey
# 主进程的管理
# github https://github.com/runhey
import asyncio
from asyncio.tasks import Task
from multiprocessing import Queue, Pipe
from threading import Thread

from module.logger import logger
from module.config.config import Config
from module.server.script_process import ScriptProcess, ScriptState
from module.server.config_manager import ConfigManager


class MainManager(ConfigManager):
    config_cache: Config = None  # 缓存当前切换的配置
    script_process: dict[str: ScriptProcess] = None  # 脚本进程
    push_data_thread: Thread = None  # 数据推送线程

    def __init__(self) -> None:
        super().__init__()
        self.script_process: dict[str: ScriptProcess] = {}  # 脚本进程
        self._all_script_files = self.all_script_files()
        for script_name in self._all_script_files:
            self.script_process[script_name] = ScriptProcess(script_name)
        self.push_data_thread = Thread(target=lambda : asyncio.run(self.push_data_handle()), daemon=True)
        self.push_data_thread.start()

    def ensure_config_cache(self, config_name):
        if self.config_cache is None:
            if config_name not in self._all_script_files:
                logger.warning(f'[{config_name}] script file does not exist')
                return None
            self.config_cache = Config(config_name)
        elif self.config_cache.config_name != config_name:
            self.config_cache = Config(config_name)
        return self.config_cache

    def add_script_file(self, file_name: str):
        # 当你添加了新的脚本文件后，需要添加缓存的列表
        if file_name in self._all_script_files:
            logger.warning(f'[{file_name}] script file already exists')
            return
        self._all_script_files = self.all_script_files()
        self.script_process[file_name] = ScriptProcess(file_name)

    async def push_data_handle(self):
        tasks : dict[str, Task] = {}
        from asyncio import sleep
        while 1:
            await sleep(5)
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
                    tasks[coroutine_state_name] = asyncio.create_task(script_p.coroutine_broadcast_state(), name=coroutine_state_name)

