# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field


class Desktop(BaseModel):
    """桌面客户端（阴阳师 PC 版）模式开关与专属参数，与 device 组并列。

    enable 为 True 时 OAS 不走 adb，直接控制本机 Windows 上的客户端窗口；
    多开账号隔离见 profile_dir。
    """

    # 启用后 device 组的模拟器参数退场，handle 改作客户端窗口标题（留空自动识别）
    enable: bool = Field(default=False, description='desktop_enable_help')
    # 游戏安装目录（含 bin\onmyoji.exe 或 Launch.exe 的根目录），留空自动查找
    game_path: str = Field(default='', description='game_path_help')
    # 多开账号隔离：实例档案目录，每个配置一个
    profile_dir: str = Field(default='', description='profile_dir_help')
    # 多开时自动摆放窗口位置，格式 "x,y"（如 0,0 / 660,0）；留空 = 不移动
    window_pos: str = Field(default='', description='window_pos_help')
    # 自定义窗口标题：绑定时改窗口标题，仅用于多开时在任务栏区分实例。
    # 留空 = 不改；识别与点击不依赖标题
    window_title: str = Field(default='', description='window_title_help')
    # 一次性按钮：点击后启动本配置对应的客户端实例；执行后自动弹回 false
    launch_instance: bool = Field(default=False, description='launch_instance_help')
