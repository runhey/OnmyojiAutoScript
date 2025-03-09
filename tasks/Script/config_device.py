# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from typing import Union
from pydantic import BaseModel, ValidationError, Field

from module.logger import logger

class PackageName(str, Enum):
    AUTO = 'auto'
    NETEASE_ONMYOJI = 'com.netease.onmyoji.wyzymnqsd_cps'  # 网易自家的阴阳师
    NETEASE_MI = 'com.netease.onmyoji.mi'  # 小米
    NETEASE = 'com.netease.onmyoji'
    NETEASE_HUAWEI = 'com.netease.onmyoji.huawei'
    NETEASE_BILIBILI = 'com.netease.onmyoji.bili'

class ScreenshotMethod(str, Enum):
    AUTO = 'auto'
    ADB = 'ADB'
    ADB_NC = 'ADB_nc'
    UIAUTOMATOR2 = 'uiautomator2'
    DROIDCAST = 'DroidCast'
    DROIDCAST_RAW = 'DroidCast_raw'
    SCRCPY = 'scrcpy'
    WINDOW_BACKGROUND = 'window_background'
    NEMU_IPC = 'nemu_ipc'

class ControlMethod(str, Enum):
    ADB = 'adb'
    UIAUTOMATOR2 = 'uiautomator2'
    MINITOUCH = 'minitouch'
    WINDOW_MESSAGE = 'window_message'

class EmulatorInfoType(str, Enum):
    # module.device.platform2.emulator_base.EmulatorBase
    AUTO = 'auto'
    NoxPlayer = 'NoxPlayer'
    NoxPlayer64 = 'NoxPlayer64'
    BlueStacks4 = 'BlueStacks4'
    BlueStacks5 = 'BlueStacks5'
    BlueStacks4HyperV = 'BlueStacks4HyperV'
    BlueStacks5HyperV = 'BlueStacks5HyperV'
    LDPlayer3 = 'LDPlayer3'
    LDPlayer4 = 'LDPlayer4'
    LDPlayer9 = 'LDPlayer9'
    MuMuPlayer = 'MuMuPlayer'
    MuMuPlayerX = 'MuMuPlayerX'
    MuMuPlayer12 = 'MuMuPlayer12'
    MEmuPlayer = 'MEmuPlayer'

class Device(BaseModel):
    serial: str = Field(default="auto",
                        description='serial_help')
    handle: str = Field(default='',
                        description='handle_help')
    package_name: PackageName = Field(title='Package Name',
                                      default=PackageName.AUTO,
                                      description='package_name_help')
    screenshot_method: ScreenshotMethod = Field(default=ScreenshotMethod.AUTO,
                                                description='screenshot_method_help')
    control_method: ControlMethod = Field(default=ControlMethod.MINITOUCH,
                                          description='control_method_help')
    adb_restart: bool = Field(default=False,
                              description='adb_restart_help')
    emulatorinfo_type: Union[EmulatorInfoType, str] = Field(default=EmulatorInfoType.AUTO,
                                                description='emulatorinfo_type_help')
    emulatorinfo_name: str = Field(default='',
                                   description='emulatorinfo_name_help')
    emulatorinfo_path: str = Field(default='',
                                   description='emulatorinfo_path_help')
    # 举例, E:\ProgramFiles\MuMuPlayer-12.0\shell\MuMuPlayer.exe
    # 模拟器启动后最小化
    emulator_window_minimize: bool = Field(default=False,
                                             description='emulator_window_minimize_help')



if __name__ == '__main__':
    d = Device()
    print(d.json())
    print(d.schema_json())
    try:
        d.control_method = 'adb'
    except ValidationError as e:
        print(e)
