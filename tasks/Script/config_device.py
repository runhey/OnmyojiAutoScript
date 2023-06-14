# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from pydantic import BaseModel, ValidationError, validator, Field

from module.logger import logger

class PackageName(str, Enum):
    AUTO = 'auto'
    NETEASE_ONMYOJI = 'com.netease.onmyoji.wyzymnqsd_cps'  # 网易自家的阴阳师

class ScreenshotMethod(str, Enum):
    ADB = 'adb'
    ADB_NC = 'adb_nc'
    UIAUTOMATOR2 = 'uiautomator2'
    DROIDCAST = 'droidcast'
    DROIDCAST_RAW = 'droidcast_raw'
    SCRCPY = 'scrcpy'
    WINDOW_BACKGROUND = 'window_background'

class ControlMethod(str, Enum):
    ADB = 'adb'
    UIAUTOMATOR2 = 'uiautomator2'
    MINITOUCH = 'minitouch'
    WINDOW_MESSAGE = 'window_message'


class Device(BaseModel):
    serial: str = Field(default="auto",
                        description='Common emulator Serial can be queried in the list belowUse "auto" to auto-detect emulators, but if multiple emulators are running or use emulators that do not support auto-detect, "auto" cannot be used and serial must be filled in manually')
    handle: str = Field(default='auto',
                        description='you can use auto or your emulator title')
    package_name: PackageName = Field(default=PackageName.AUTO,
                                      description='package name')
    screenshot_method: ScreenshotMethod = Field(default=ScreenshotMethod.WINDOW_BACKGROUND,
                                                description='only support window')
    control_method: ControlMethod = Field(default=ControlMethod.WINDOW_MESSAGE,
                                          description='only support window')
    adb_restart: bool = Field(default=False,
                              description='')



if __name__ == '__main__':
    d = Device()
    print(d.json())
    print(d.schema_json())
    try:
        d.control_method = 'adb'
    except ValidationError as e:
        print(e)
