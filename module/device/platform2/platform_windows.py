import ctypes
import re
import subprocess
import psutil
from adbutils import AdbDevice, AdbClient

from deploy.utils import DataProcessInfo
from module.base.decorator import run_once
from module.base.timer import Timer
from module.device.handle import Handle
from module.device.platform2.platform_base import PlatformBase
from module.device.platform2.emulator_windows import Emulator, EmulatorInstance, EmulatorManager
from module.logger import logger

import ctypes
from ctypes import wintypes


class EmulatorUnknown(Exception):
    pass

def minimize_by_name(window_name, convert_hidden=True):
    """
    按名称处理窗口状态
    Args:
        window_name (str): 窗口名称（支持部分匹配）
        convert_hidden (bool): 是否将隐藏窗口改为最小化
    """
    def callback(hwnd, lParam):
        title = get_window_title(hwnd)
        if window_name.lower() in title.lower():
            # 检查窗口当前状态
            is_visible = ctypes.windll.user32.IsWindowVisible(hwnd)
            
            if is_visible:
                # 可见窗口 → 最小化
                minimize_window(hwnd)
                logger.info(f'最小化可见窗口: {title}')
            elif convert_hidden:
                # 隐藏窗口 → 改为最小化不激活
                ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_SHOWMINNOACTIVE
                logger.info(f'隐藏窗口改为最小化: {title}')
        return True
    
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, ctypes.POINTER(ctypes.c_int))
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), None)

def find_hwnd_by_name(window_name):
    """
    枚举所有窗口，返回第一个匹配名称的 hwnd
    """
    target = None
    def callback(hwnd, lParam):
        title = get_window_title(hwnd)
        if window_name.lower() in title.lower():
            nonlocal target
            target = hwnd
            return False  # 停止枚举
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, ctypes.POINTER(ctypes.c_int))
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), None)
    return target
def show_window_by_name(window_name):
    """
    显示指定名称的窗口
    Args:
        window_name (str): 窗口名称（支持部分匹配）
    """
    hwnd = find_hwnd_by_name(window_name)
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
        set_focus_window(hwnd)
        logger.info(f'显示窗口: {window_name}')
    else:
        logger.info(f'没有找到窗口: {window_name}')

def get_focused_window():
    return ctypes.windll.user32.GetForegroundWindow()


def set_focus_window(hwnd):
    ctypes.windll.user32.SetForegroundWindow(hwnd)


def minimize_window(hwnd):
    ctypes.windll.user32.ShowWindow(hwnd, 6)


def get_window_title(hwnd):
    """Returns the window title as a string."""
    text_len_in_characters = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    string_buffer = ctypes.create_unicode_buffer(
        text_len_in_characters + 1)  # +1 for the \0 at the end of the null-terminated string.
    ctypes.windll.user32.GetWindowTextW(hwnd, string_buffer, text_len_in_characters + 1)
    return string_buffer.value


def flash_window(hwnd, flash=True):
    ctypes.windll.user32.FlashWindow(hwnd, flash)


class AdbDeviceWithStatus(AdbDevice):
    def __init__(self, client: AdbClient, serial: str, status: str):
        self.status = status
        super().__init__(client, serial)

    def __str__(self):
        return f'AdbDevice({self.serial}, {self.status})'

    __repr__ = __str__

    def __bool__(self):
        return True

class PlatformWindows(PlatformBase, EmulatorManager):
    @classmethod
    def execute(cls, command, show_window=True):
        """
        Args:
            command (str):

        Returns:
            subprocess.Popen:
        """

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        if not show_window:
            startupinfo.wShowWindow = 0  # SW_MINIMIZE - 不显示窗口
        else:
            startupinfo.wShowWindow = 1  # SW_SHOWNORMAL - 正常显示


        command = command.replace(r"\\", "/").replace("\\", "/").replace('"', '"')
        logger.info(f'Execute: {command}')
        return subprocess.Popen(
        command,
        close_fds=True,
        startupinfo=startupinfo
        )
        #return subprocess.Popen(command, close_fds=True)  # only work on Windows

    @classmethod
    def kill_process_by_regex(cls, regex: str) -> int:
        """
        Kill processes with cmdline match the given regex.

        Args:
            regex:

        Returns:
            int: Number of processes killed
        """
        count = 0

        for proc in psutil.process_iter():
            cmdline = DataProcessInfo(proc=proc, pid=proc.pid).cmdline
            if re.search(regex, cmdline):
                logger.info(f'Kill emulator: {cmdline}')
                proc.kill()
                count += 1

        return count

    def _emulator_start(self, instance: EmulatorInstance):
        """
        Start a emulator without error handling
        """
        show_window=not self.config.script.device.emulator_window_minimize and not self.config.script.device.run_background_only
        exe: str = instance.emulator.path
        if instance == Emulator.MuMuPlayer:
            # NemuPlayer.exe
            self.execute(exe, show_window=show_window)
        elif instance == Emulator.MuMuPlayerX:
            # NemuPlayer.exe -m nemu-12.0-x64-default
            self.execute(f'"{exe}" -m {instance.name}', show_window=show_window)
        elif instance == Emulator.MuMuPlayer12:
            # MuMuPlayer.exe -v 0
            if instance.MuMuPlayer12_id is None:
                logger.warning(f'Cannot get MuMu instance index from name {instance.name}')
            self.execute(f'"{exe}" -v {instance.MuMuPlayer12_id}', show_window=show_window)
        elif instance == Emulator.LDPlayerFamily:
            # ldconsole.exe launch --index 0
            self.execute(f'"{Emulator.single_to_console(exe)}" launch --index {instance.LDPlayer_id}', show_window=show_window)
        elif instance == Emulator.NoxPlayerFamily:
            # Nox.exe -clone:Nox_1
            self.execute(f'"{exe}" -clone:{instance.name}', show_window=show_window)
        elif instance == Emulator.BlueStacks5:
            # HD-Player.exe --instance Pie64
            self.execute(f'"{exe}" --instance {instance.name}', show_window=show_window)
        elif instance == Emulator.BlueStacks4:
            # Bluestacks.exe -vmname Android_1
            self.execute(f'"{exe}" -vmname {instance.name}', show_window=show_window)
        elif instance == Emulator.MEmuPlayer:
            # MEmu.exe MEmu_0
            self.execute(f'"{exe}" {instance.name}', show_window=show_window)
        else:
            raise EmulatorUnknown(f'Cannot start an unknown emulator instance: {instance}')

    def _emulator_stop(self, instance: EmulatorInstance):
        """
        Stop a emulator without error handling
        """
        exe: str = instance.emulator.path
        if instance == Emulator.MuMuPlayer:
            # MuMu6 does not have multi instance, kill one means kill all
            # Has 4 processes
            # "C:\Program Files\NemuVbox\Hypervisor\NemuHeadless.exe" --comment nemu-6.0-x64-default --startvm
            # "E:\ProgramFiles\MuMu\emulator\nemu\EmulatorShell\NemuPlayer.exe"
            # E:\ProgramFiles\MuMu\emulator\nemu\EmulatorShell\NemuService.exe
            # "C:\Program Files\NemuVbox\Hypervisor\NemuSVC.exe" -Embedding
            self.kill_process_by_regex(
                rf'('
                rf'NemuHeadless.exe'
                rf'|NemuPlayer.exe\"'
                rf'|NemuPlayer.exe$'
                rf'|NemuService.exe'
                rf'|NemuSVC.exe'
                rf')'
            )
        elif instance == Emulator.MuMuPlayerX:
            # MuMu X has 3 processes
            # "E:\ProgramFiles\MuMu9\emulator\nemu9\EmulatorShell\NemuPlayer.exe" -m nemu-12.0-x64-default -s 0 -l
            # "C:\Program Files\Muvm6Vbox\Hypervisor\Muvm6Headless.exe" --comment nemu-12.0-x64-default --startvm xxx
            # "C:\Program Files\Muvm6Vbox\Hypervisor\Muvm6SVC.exe" --Embedding
            self.kill_process_by_regex(
                rf'('
                rf'NemuPlayer.exe.*-m {instance.name}'
                rf'|Muvm6Headless.exe'
                rf'|Muvm6SVC.exe'
                rf')'
            )
        elif instance == Emulator.MuMuPlayer12:
            # MuMuManager.exe api -v 1 shutdown_player
            if instance.MuMuPlayer12_id is None:
                logger.warning(f'Cannot get MuMu instance index from name {instance.name}')
            self.execute(f'"{Emulator.single_to_console(exe)}" api -v {instance.MuMuPlayer12_id} shutdown_player')
        elif instance == Emulator.LDPlayerFamily:
            # ldconsole.exe quit --index 0
            self.execute(f'"{Emulator.single_to_console(exe)}" quit --index {instance.LDPlayer_id}')
        elif instance == Emulator.NoxPlayerFamily:
            # Nox.exe -clone:Nox_1 -quit
            self.execute(f'"{exe}" -clone:{instance.name} -quit')
        elif instance == Emulator.BlueStacks5:
            # BlueStack has 2 processes
            # C:\Program Files\BlueStacks_nxt_cn\HD-Player.exe --instance Pie64
            # C:\Program Files\BlueStacks_nxt_cn\BstkSVC.exe -Embedding
            self.kill_process_by_regex(
                rf'('
                rf'HD-Player.exe.*"--instance" "{instance.name}"'
                rf')'
            )
        elif instance == Emulator.BlueStacks4:
            # E:\Program Files (x86)\BluestacksCN\bsconsole.exe quit --name Android
            self.execute(f'"{Emulator.single_to_console(exe)}" quit --name {instance.name}')
        elif instance == Emulator.MEmuPlayer:
            # F:\Program Files\Microvirt\MEmu\memuc.exe stop -n MEmu_0
            self.execute(f'"{Emulator.single_to_console(exe)}" stop -n {instance.name}')
        else:
            raise EmulatorUnknown(f'Cannot stop an unknown emulator instance: {instance}')

    def _emulator_function_wrapper(self, func: callable):
        """
        Args:
            func (callable): _emulator_start or _emulator_stop

        Returns:
            bool: If success
        """
        try:
            func(self.emulator_instance)
            return True
        except OSError as e:
            msg = str(e)
            # OSError: [WinError 740] 请求的操作需要提升。
            if 'WinError 740' in msg:
                logger.error('To start/stop MumuAppPlayer, ALAS needs to be run as administrator')
        except EmulatorUnknown as e:
            logger.error(e)
        except Exception as e:
            logger.exception(e)

        logger.error(f'Emulator function {func.__name__}() failed')
        return False

    def emulator_start_watch(self):
        """
        Returns:
            bool: True if startup completed
                False if timeout, unexpected stop, adb preemptive
        """
        logger.hr('Emulator start', level=2)
        current_window = get_focused_window()
        serial = self.emulator_instance.serial
        logger.info(f'Current window: {current_window}')

        def adb_connect():
            m = self.adb_client.connect(self.serial)
            if 'connected' in m:
                # Connected to 127.0.0.1:59865
                # Already connected to 127.0.0.1:59865
                return False
            elif '(10061)' in m:
                # cannot connect to 127.0.0.1:55555:
                # No connection could be made because the target machine actively refused it. (10061)
                return False
            else:
                return True

        @run_once
        def show_online(m):
            logger.info(f'Emulator online: {m}')

        @run_once
        def show_ping(m):
            logger.info(f'Command ping: {m}')

        @run_once
        def show_package(m):
            logger.info(f'Found azurlane packages: {m}')

        interval = Timer(1).start()
        timeout = Timer(120).start()
        struct_window = Timer(10)
        new_window = 0
        while 1:
            interval.wait()
            interval.reset()
            if timeout.reached():
                logger.warning(f'Emulator start timeout')
                return False

            # Check emulator window showing up
            # logger.info([get_focused_window(), get_window_title(get_focused_window())])
            if current_window != 0 and new_window == 0:
                new_window = get_focused_window()
                if current_window != new_window and not self.config.script.device.emulator_window_minimize and not self.config.script.device.run_background_only:
                    logger.info(f'New window showing up: {new_window}, focus back')
                    set_focus_window(current_window)
                else:
                    new_window = 0
            try:
                logger.info(f'Try to connect emulator, remain[{timeout.remain():.1f}s]')
                # Check device connection
                devices = self.list_device().select(serial=serial)
                # logger.info(devices)
                if devices:
                    device: AdbDeviceWithStatus = devices.first_or_none()
                    if device.status == 'device':
                        # Emulator online
                        pass
                    if device.status == 'offline':
                        self.adb_client.disconnect(serial)
                        adb_connect()
                        continue
                else:
                    # Try to connect
                    adb_connect()
                    continue
            except Exception as e:
                logger.warning(f'Error during adb_connect in watch loop: {e}')
                return False

            show_online(devices.first_or_none())

            # Check command availability
            try:
                pong = self.adb_shell(['echo', 'pong'])
            except Exception as e:
                logger.info(e)
                continue
            show_ping(pong)

            # Check game package
            packages = self.list_app_packages(show_log=False)
            if len(packages):
                pass
            else:
                continue
            show_package(packages)

            # Check Window structure
            if not struct_window.started():
                struct_window.start()
            elif struct_window.reached():
                break
            if new_window == 0:
                continue
            if not Handle.handle_has_children(hwnd=new_window):
                continue

            # All check passed
            break

        emulator_window_minimize = self.config.script.device.emulator_window_minimize
        if (emulator_window_minimize): logger.info(f'Minimize new emulator window: {emulator_window_minimize}')
        if (self.config.script.device.run_background_only):
            logger.info(f'run background only: {self.config.script.device.run_background_only}')
            logger.warning('run_background_only will not show any UI, emulator will run background only')
        if emulator_window_minimize and not self.config.script.device.run_background_only:
            # 直接使用窗口名称最小化
            sleep_time = 3
            logger.info(f'Waiting {sleep_time} seconds before minimizing window')
            Timer(sleep_time).wait()
            target_window_name = self.config.script.device.handle  # 在这里输入你的具体窗口名称
            minimize_by_name(target_window_name)
            logger.info(f'最小化窗口: {target_window_name}')
            # if current_window:
            #     logger.info(f'De-flash current window: {current_window}')
            #     flash_window(current_window, flash=False)

        logger.info('Emulator start completed')
        return True


    def emulator_start(self):
        logger.hr('Emulator start', level=1)
        for i in range(3):
            # Stop
            if not self._emulator_function_wrapper(self._emulator_stop):
                return False
            # Start
            if self._emulator_function_wrapper(self._emulator_start):
                # Success
                if self.emulator_start_watch():
                    return True
                logger.attr(2 - i, f'Failed to connect or start, try again')
                continue
            else:
                # Failed to start, stop and start again
                if self._emulator_function_wrapper(self._emulator_stop):
                    continue
                else:
                    return False

        logger.error('Failed to start emulator 3 times, stopped')
        return False

    def emulator_stop(self):
        logger.hr('Emulator stop', level=1)
        for _ in range(3):
            # Stop
            if self._emulator_function_wrapper(self._emulator_stop):
                # Success
                return True
            else:
                # Failed to stop, start and stop again
                if self._emulator_function_wrapper(self._emulator_start):
                    continue
                else:
                    return False

        logger.error('Failed to stop emulator 3 times, stopped')
        return False


if __name__ == '__main__':
    self = PlatformWindows()
    d = self.emulator_instance
    print(d)
