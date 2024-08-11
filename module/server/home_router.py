# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from fastapi import APIRouter

from module.logger import logger
from module.server.main_manager import MainManager
from module.server.updater import Updater

home_app = APIRouter(
    prefix="/home",
    tags=["home"],
)


@home_app.get('/test')
async def home_test():
    return {'message': 'test'}


#  gcc -Wall -pedantic -shared -fPIC -o group_work.so group_work.c -lwiringPi
@home_app.get('/home_menu')
async def home_menu():
    return {'Home': [], 'Updater': [], 'Tool': []}


@home_app.post('/notify_test')
async def notify_test(setting: str, title: str, content: str):
    from module.notify.notify import Notifier
    try:
        notifier = Notifier(setting, True)
        if notifier.push(title=title, content=content):
            del notifier
            return True
        else:
            del notifier
            return False
    except Exception as e:
        logger.exception(e)
        return str(e)


@home_app.get('/kill_server')
async def kill_server():
    MainManager.signal_kill_server = True
    return 'success'


@home_app.get('/update_info')
async def update_info():
    try:
        updater = Updater()
        result = {'is_update': updater.check_update(),
                  'branch': updater.current_branch(),
                  'current_commit': updater.current_commit(),
                  'latest_commit': updater.latest_commit(),
                  'commit': updater.get_commit(n=15),
                  }
        return result
    except Exception as e:
        logger.error(e)
        return None

@home_app.get('/execute_update')
async def execute_update():
    # 下拉仓库 -> 关闭所有脚本进程 -> 最后重启oasx
    try:
        updater = Updater()
        updater.execute_pull()
    except Exception as e:
        logger.error(e)
    return '手动更新将会立即结束运行中的脚本服务, 最后你还需重启oasx'

