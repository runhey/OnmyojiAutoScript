# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.gui.context.add import Add
from module.gui.context.process_manager import ProcessManager
from module.gui.fluent_app import FluentApp

if __name__ == "__main__":
    # 检查是不是以管理员身份运行，脚本启动的其他进程会继承权限

    # 启动一个UI交互的线程，因为信号槽不可跨进程
    # 后面选择注入上下文快
    app = FluentApp()
    add_config = Add()
    process_manager = ProcessManager()
    # process_manager.create_all()

    app.set_context_property(add_config, 'add_config')
    app.set_context_property(process_manager, 'process_manager')
    # 启动一个GUI
    app.run()
