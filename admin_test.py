# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey



from module.gui.utils import check_admin



if __name__ == "__main__":
    # 检查是不是以管理员身份运行，脚本启动的其他进程会继承权限
    # 但是貌似有问题的这个函数
    check_admin()





