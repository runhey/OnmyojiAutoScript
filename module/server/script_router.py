# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from fastapi import APIRouter

from module.logger import logger
from module.server.main_manager import MainManager
from module.server.script_process import ScriptProcess

script_app = APIRouter()
mm = MainManager()

@script_app.get('/test')
async def script_test():
    return {'message':'test'}

@script_app.get('/script_menu')
async def script_menu():
    if mm.config_cache is None:
        logger.warning('未加载配置')
        return {'message':'未加载配置'}
    return mm.config_cache.gui_menu
# ----------------------------------   配置文件管理   ----------------------------------
@script_app.get('/config_list')
async def config_list():
    return mm.all_script_files()

@script_app.post('/config_copy')
async def config_copy(file: str, template: str = 'template'):
    mm.copy(file, template)
    return mm.all_script_files()


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
    if not mm.ensure_config_cache(task):
        raise Exception(f'[{script_name}] script file does not exist')
    return mm.config_cache.get_task_args(task)

@script_app.put('/{script_name}/{task}/{group}/{argument}/value/{value}')
async def script_task(script_name: str, task: str, group: str, argument: str, value):
    if not mm.ensure_config_cache(task):
        raise Exception(f'[{script_name}] script file does not exist')
    mm.config_cache.set_task_args(task, group, argument, value)
    return




