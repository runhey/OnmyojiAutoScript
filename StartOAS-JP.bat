::Change UTF-8


:: Check Admin
icacls "%SYSTEMROOT%\system32\config\system" > nul 2>&1


::"D:\Program Files\OnmyojiAutoScript-MG\oas.exe"

::"D:\Program Files\Netease\MuMuPlayer-12.0\shell\MuMuManager.exe" control -v all launch  -pkg com.netease.onmyoji.wyzymnqsd_cps

@rem
@echo off
color F0
title Oas Start
set "_pyBin=D:\Program Files\OnmyojiAutoScript-MG\toolkit"
set "_GitBin=D:\Program Files\OnmyojiAutoScript-MG\toolkit\Git\mingw64\bin"
set "_adbBin=D:\Program Files\OnmyojiAutoScript-MG\toolkit\Lib\site-packages\adbutils\binaries"
set "PATH=%_root%\toolkit\alias;%_root%\toolkit\command;%_pyBin%;%_pyBin%\Scripts;%_GitBin%;%_adbBin%;%PATH%"

@echo Start Oas
start  python "D:\Py Program\OnmyojiAutoScript-MG\server.py"
timeout /t 2

@echo Start Oasx
start "oasx" "D:\Program Files\oasx\oasx.exe"
timeout /t 5 /nobreak > nul  # 延迟5秒退出
exit
