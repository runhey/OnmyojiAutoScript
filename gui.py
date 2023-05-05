# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.gui.fluent_app import FluentApp

if __name__ == "__main__":
    # 检查是不是以管理员身份运行，脚本启动的其他进程会继承权限
    # 启动一个UI交互的线程，因为信号槽不可跨进程
    # 启动一个GUI
    FluentApp().run()
