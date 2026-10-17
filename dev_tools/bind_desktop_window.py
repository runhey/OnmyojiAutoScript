# -*- coding: utf-8 -*-
"""桌面客户端模式配置工具
============================
把指定 OAS 配置切到桌面客户端模式（script.desktop.enable=True、
screenshot_method='window_background'、control_method='window_message'），
并可顺带启动一个实例验证安装目录与档案配置是否可用。

PID 不再写进配置：客户端进程 PID 每次重启都会变，OAS 启动/认领时自动绑定，
档案目录内会写 oas_instance.json 运行时状态供下次认领（多开账号隔离）。

用法:
    ./toolkit/python.exe -m dev_tools.bind_desktop_window --config oas1
    ./toolkit/python.exe -m dev_tools.bind_desktop_window --config oas1 --path D:\\yys
    ./toolkit/python.exe -m dev_tools.bind_desktop_window --config oas1 --profile D:\\yys-profiles\\p1 --launch
"""
import argparse

from module.config.config import Config
from module.logger import logger


def bind_desktop_mode(config_name: str, game_path: str = '', profile_dir: str = '') -> None:
    """把配置切到桌面客户端模式（幂等，可重复执行）。"""
    config = Config(config_name)
    config.script.desktop.enable = True
    if game_path:
        config.script.desktop.game_path = game_path
    if profile_dir:
        config.script.desktop.profile_dir = profile_dir
    # PrintWindow 对客户端的 DirectX 渲染窗口返回纯黑，桌面模式统一用 BitBlt
    config.script.device.screenshot_method = 'window_background'
    config.script.device.control_method = 'window_message'
    config.save()
    logger.info(f'Config [{config_name}] switched to desktop client mode '
                f'(game_path={config.script.desktop.game_path or "auto"}, '
                f'profile_dir={config.script.desktop.profile_dir or "-"})')


def launch_and_check(config_name: str) -> None:
    """按当前 desktop 配置启动一个实例并校准窗口尺寸，验证配置可用。"""
    from module.device.device import Device
    from module.device.method.desktop_impl import desktop_launch_instance

    config = Config(config_name)
    if not desktop_launch_instance(config):
        logger.error('启动失败，请检查 游戏安装目录 / 档案目录 配置')
        return
    device = Device(config)
    device.desktop_window_set_size()
    logger.info('桌面客户端已启动并完成窗口校准，可以启动脚本了')


def main():
    parser = argparse.ArgumentParser(description='把 OAS 配置切换到桌面客户端模式')
    parser.add_argument('--config', required=True, help='配置实例名，如 oas1')
    parser.add_argument('--path', default='', help='游戏安装目录（含 bin\\onmyoji.exe 的根目录）')
    parser.add_argument('--profile', default='', help='多开档案目录（每个配置一个，实现账号隔离）')
    parser.add_argument('--launch', action='store_true',
                        help='切换后立即启动一个客户端实例并校准窗口尺寸')
    args = parser.parse_args()

    bind_desktop_mode(args.config, args.path, args.profile)
    if args.launch:
        launch_and_check(args.config)


if __name__ == '__main__':
    main()
