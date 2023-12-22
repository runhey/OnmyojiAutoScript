# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import ctypes
import time
import psutil



# 定义Windows API函数
kernel32 = ctypes.WinDLL('kernel32')
SetConsoleTitleW = kernel32.SetConsoleTitleW

# 设置进程名称
new_title = "Netle"
SetConsoleTitleW(new_title)


processes = psutil.process_iter()
for process in processes:
    if not process.name().startswith('python'):
        continue
    print(f"进程ID: {process.pid}, 名字: {process.name()}")

time.sleep(3)
