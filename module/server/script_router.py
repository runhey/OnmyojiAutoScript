# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from module.config.config import Config

from module.logger import logger
from module.server.main_manager import MainManager
from module.server.script_process import ScriptProcess


script_app = APIRouter()
mm = MainManager()

@script_app.get('/test')
async def script_test():
    return 'success'

@script_app.get('/script_menu')
async def script_menu():
    if mm.config_cache is None:
        mm.config_cache = Config('template')
    return mm.config_cache.gui_menu_list
# ----------------------------------   配置文件管理   ----------------------------------
@script_app.get('/config_list')
async def config_list():
    return mm.all_script_files()

@script_app.post('/config_copy')
async def config_copy(file: str, template: str = 'template'):
    mm.copy(file, template)
    return mm.all_script_files()

@script_app.get('/config_new_name')
async def config_new_name():
    return mm.generate_script_name()

@script_app.get('/config_all')
async def config_all():
    return mm.all_json_file()


# ---------------------------------   脚本实例管理   ----------------------------------
@script_app.get('/{script_name}/start')
async def script_start(script_name: str):
    if script_name not in mm.script_process:
        mm.script_process[script_name] = ScriptProcess(script_name)
    mm.script_process[script_name].start()
    return

@script_app.get('/{script_name}/stop')
async def script_stop(script_name: str):
    if script_name not in mm.script_process:
        logger.warning(f'[{script_name}] script process does not exist')
        return
    mm.script_process[script_name].stop()
    return

@script_app.get('/{script_name}/{task}/args')
async def script_task(script_name: str, task: str):
    if not mm.ensure_config_cache(script_name):
        raise Exception(f'[{script_name}] script file does not exist')
    return mm.config_cache.model.script_task(task)

@script_app.put('/{script_name}/{task}/{group}/{argument}/value/{value}')
async def script_task(script_name: str, task: str, group: str, argument: str, value):
    if not mm.ensure_config_cache(task):
        raise HTTPException(status_code=404, detail=f'[{script_name}] script file does not exist')
    mm.config_cache.set_task_args(task, group, argument, value)
    return

# --------------------------------------  SSE  --------------------------------------
@script_app.get('/{script_name}/state')
async def script_task_state(script_name: str):
    async def state_generate_events():
        while True:
            # 生成 SSE 事件数据
            event_data = "data: Hello, SSE!\n\n"
            yield event_data

            # 模拟异步操作，可以替换为您的实际处理逻辑
            await asyncio.sleep(1)

    response = StreamingResponse(state_generate_events(), media_type="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    return response

@script_app.get('/{script_name}/log')
async def script_task_log(script_name: str):
    async def log_generate_events():
        while True:
            # 生成 SSE 事件数据
            event_data = "data: log\n"
            yield event_data

            # 模拟异步操作，可以替换为您的实际处理逻辑
            await asyncio.sleep(1)

    response = StreamingResponse(log_generate_events(), media_type="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    return response

