# This Python file uses the following encoding: utf-8
"""桌面客户端（阴阳师 PC 版）窗口控制实现。

从 module/device/handle.py 拆出：桌面模式与模拟器模式除"窗口句柄怎么拿到"外没有
任何共享逻辑，两者同处一个类会把 handle.py 撑到 1300+ 行，也让"移植到底动没动
模拟器基线"难以一眼看清。这里用纯 mixin ``DesktopWindow`` 承载全部桌面分支
（``Handle`` 继承它），handle.py 只保留模拟器逻辑与少量桌面内联判断。

边界约定：
- ``DesktopWindow`` 不定义 ``__init__``，全部实例状态由 ``Handle.__init__`` 的
  桌面分支设置；类内方法名与 Handle 模拟器方法无重名，MRO 无歧义；
- 本模块不反向依赖 handle.py，是叶子模块，无循环导入；
- 模块级常量与 helper（``list_desktop_windows`` / ``desktop_window_option`` /
  ``desktop_option2pid`` / ``dpi_awareness`` 等）一并住在这里，外部调用方直接
  从本模块导入，不经 handle.py 转出——避免"补丁打在转出别名上静默失效"。
"""

import os
import re
import subprocess
import time
import ctypes
from ctypes import c_long, byref, POINTER, Structure, wintypes

from contextlib import contextmanager
from pathlib import Path

from win32api import SendMessage
from win32process import GetWindowThreadProcessId
from win32gui import (GetWindowText, EnumWindows, GetWindowRect, IsWindow,
                      GetClientRect, ClientToScreen, GetWindowLong,
                      SetWindowPos, GetClassName, IsIconic, ShowWindow)
from win32con import (WM_KEYDOWN, WM_KEYUP, VK_RETURN, GWL_STYLE, GWL_EXSTYLE,
                      HWND_TOP, SWP_NOMOVE, SWP_SHOWWINDOW, SW_RESTORE)

from module.base.decorator import del_cached_property
from module.exception import EmulatorNotRunningError
from module.logger import logger


# 桌面客户端窗口标题（官方桌面版，多开共用同一标题）
DESKTOP_WINDOW_TITLES = ('阴阳师-网易游戏', '阴阳师-MuMu模拟器专版')
# 「进程活着但窗口还没就绪」时的等待上限（秒）与轮询间隔。空窗期有两种：客户端
# 启动期还没出窗口、确认 MPay 弹窗后销毁登录界面重建主窗口的那几秒。这段等待只
# 轮询窗口，绝不重新启动进程——把「窗口暂时不在」当成「客户端没在运行」会拉起
# 多余实例（单实例语义下用户正在用的那个会被顶掉），并把配置里的 handle 覆盖成新实例
DESKTOP_WINDOW_READY_WAIT = 15
DESKTOP_WINDOW_READY_POLL_INTERVAL = 0.5

# 网易 MPay 账号登录弹窗的窗口类名。它是与游戏主窗口同 PID 的独立顶层窗口
# （DirectUI 绘制，无子控件），不在游戏渲染面内，因此主窗口 BitBlt 截不到它，
# 也无法用图像识别处理，只能按类名单独定位并注入消息。
DESKTOP_LOGIN_POPUP_CLASS = 'MPAY_LOGIN'

# 调整窗口尺寸时撞上客户端重建窗口的重试轮数与间隔（秒）。客户端确认登录弹窗后销毁
# 登录界面、重建游戏主窗口，实测这段空窗期在几百毫秒到数秒之间，6 轮 × 1s 足够覆盖
DESKTOP_RESIZE_ATTEMPTS = 6
DESKTOP_RESIZE_RETRY_INTERVAL = 1.0
# 关闭桌面客户端的强杀轮数。TerminateProcess 可能因权限被拒（实测本机出现过
# (5, '拒绝访问。')），也可能进程正在退出但还没消失，因此杀完必须验证进程真的没了，
# 没死就再杀一轮，而不是发完指令就当成功
DESKTOP_KILL_ATTEMPTS = 3
DESKTOP_KILL_POLL_INTERVAL = 0.5

# DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2，SetThreadDpiAwarenessContext 的入参
_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

# 桌面客户端运行期间强制保持显示器常亮：桌面模式截图走 BitBlt，依赖 DWM 合成，
# 屏幕一旦因电源超时关闭，DWM 停止合成，BitBlt 只能返回静止黑帧，登录循环会因此
# 死等 300s 超时。在客户端启动时开启、关闭时清除，只锁客户端生命周期，不影响
# OAS 空闲时用户正常让屏幕休眠。
ES_CONTINUOUS = 0x80000000
ES_DISPLAY_REQUIRED = 0x00000002


@contextmanager
def dpi_awareness():
    """临时把当前线程切到 Per-Monitor V2 DPI 感知，退出时恢复原上下文。

    OAS 进程自身未声明 DPI 感知，GDI 调用默认被系统虚拟化成逻辑像素：125% 缩放下
    物理 1280x720 的客户区只报 1024x576，BitBlt 也只能取到画面左上角那一块（右侧
    侧边栏与底部菜单栏直接丢失）。桌面客户端进程是 Per-Monitor DPI 感知、按物理
    像素原生渲染，因此桌面分支的窗口测量与截图必须在感知上下文里做才能拿到完整的
    物理像素画面。用线程级而非进程级，是为了不影响模拟器直控路径既有的逻辑像素假设。
    """
    user32 = ctypes.windll.user32
    previous = None
    try:
        previous = user32.SetThreadDpiAwarenessContext(_PER_MONITOR_AWARE_V2)
    except AttributeError:
        # Windows 10 1607 以前没有该 API，退化为原有逻辑像素行为
        pass
    try:
        yield
    finally:
        if previous:
            user32.SetThreadDpiAwarenessContext(previous)


def desktop_keep_screen_on(enable: bool) -> None:
    """按桌面客户端生命周期开关「强制保持显示器常亮」。

    SetThreadExecutionState 是线程级状态：ES_CONTINUOUS 保持该线程的请求，直到
    再次调用清除。OAS worker 的任务在同一长驻线程内启停客户端，因此这里设置即可。

    注意 ES_DISPLAY_REQUIRED 只「阻止未来关闭」，屏幕若已因电源超时熄灭，必须先用
    SC_MONITORPOWER(-1) 广播把显示器物理点亮，否则 BitBlt 仍返回黑帧。
    """
    if enable:
        # 物理点亮：SC_MONITORPOWER(-1) 单独发消息对部分显示器/驱动不触发硬件唤醒
        # （实测只发它屏幕仍黑），必须再模拟一次无害键盘输入与鼠标移动，产生真实
        # 输入事件才能真正点亮。VK_F15(0x7E) 无副作用，不会干扰游戏。
        try:
            # 必须用 SendMessageTimeoutW 而不是 SendMessageW：目标是
            # HWND_BROADCAST(0xFFFF)，SendMessageW 会同步等系统里每一个顶层窗口
            # 处理完才返回，只要有一个窗口消息循环繁忙或无响应就永久阻塞调用线程
            # （实测 pytest 里这一行挂死 26 分钟不返回，生产上等于 worker 线程卡住）。
            # SMTO_ABORTIFHUNG(0x0002) 遇到无响应窗口直接放弃，1000ms 上限兜底。
            ctypes.windll.user32.SendMessageTimeoutW(
                0xFFFF, 0x0111, 0xF170, -1, 0x0002, 1000, None)
        except Exception as e:
            logger.warning(f'SC_MONITORPOWER wake failed: {e}')
        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(0x7E, 0, 0, 0)
            user32.keybd_event(0x7E, 0, 2, 0)
            user32.SetCursorPos(400, 300)
        except Exception as e:
            logger.warning(f'wake input failed: {e}')
    state = ES_CONTINUOUS | (ES_DISPLAY_REQUIRED if enable else 0)
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(state)
        logger.info(f'Desktop screen keep-awake {"ON" if enable else "OFF"}')
    except Exception as e:
        logger.warning(f'SetThreadExecutionState({enable}) failed: {e}')


def _window_total_size(width: int, height: int, style: int, ex_style: int) -> tuple:
    """用 user32.AdjustWindowRectEx 计算包含标题栏/边框的窗口总尺寸 (w, h)。

    pywin32 未导出 AdjustWindowRectEx，故用 ctypes 调用。
    """
    user32 = ctypes.windll.user32

    class RECT(Structure):
        _fields_ = [('left', c_long), ('top', c_long), ('right', c_long), ('bottom', c_long)]

    user32.AdjustWindowRectEx.argtypes = [POINTER(RECT), c_long, c_long, c_long]
    user32.AdjustWindowRectEx.restype = wintypes.BOOL
    rect = RECT(0, 0, width, height)
    user32.AdjustWindowRectEx(byref(rect), style, False, ex_style)
    return rect.right - rect.left, rect.bottom - rect.top


def _desktop_process_image(pid) -> str:
    """返回进程 exe 完整路径；打开/查询失败（已退出、权限）返回空串。"""
    kernel32 = ctypes.windll.kernel32
    # PROCESS_QUERY_LIMITED_INFORMATION
    handle = kernel32.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return ''
    try:
        buf = ctypes.create_unicode_buffer(520)
        size = ctypes.c_ulong(520)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ''
    finally:
        kernel32.CloseHandle(handle)


def _desktop_pid_under_root(pid, root) -> bool:
    """窗口归属进程的 exe 是否位于客户端安装目录之下。

    自动启动绑定时用于排除同标题的模拟器窗口（MuMu 专版窗口标题也在
    DESKTOP_WINDOW_TITLES 内），保证绑到的一定是安装目录拉起的客户端进程。
    """
    exe = _desktop_process_image(pid)
    if not exe:
        return False
    root = os.path.normcase(os.path.normpath(root))
    exe = os.path.normcase(os.path.normpath(exe))
    return exe.startswith(root + os.sep)


def list_desktop_windows() -> list:
    """枚举当前所有桌面客户端窗口。

    返回 [{'pid': int, 'title': str, 'x': int, 'y': int}]，按屏幕位置排序。
    桌面客户端多开时窗口标题完全相同，只能靠 PID 区分，附带左上角坐标是为了
    让用户在界面上按"窗口摆在哪"对号入座。按坐标排序保证同一组窗口每次枚举
    顺序稳定（EnumWindows 的返回顺序随 Z 序变化）。
    """
    def enum_cb(hwnd, param):
        param.append(hwnd)
        return True

    handles = []
    EnumWindows(enum_cb, handles)
    result = []
    for hwnd in handles:
        if GetWindowText(hwnd) not in DESKTOP_WINDOW_TITLES:
            continue
        try:
            rect = GetWindowRect(hwnd)
        except Exception:
            # 窗口在枚举与取矩形之间被关闭，跳过即可
            continue
        result.append({
            'pid': GetWindowThreadProcessId(hwnd)[1],
            'title': GetWindowText(hwnd),
            'hwnd': hwnd,
            'x': rect[0],
            'y': rect[1],
        })
    result.sort(key=lambda w: (w['x'], w['y'], w['pid']))
    return result


def desktop_window_option(window: dict) -> str:
    """把窗口信息格式化成界面下拉项文本，形如 `27272 (154,38)`。

    不显示窗口标题：桌面客户端多开时标题完全相同，且中文字样在英文界面里冗余。
    PID 放在最前，desktop_option2pid 只认第一段数字，坐标纯属给用户辨识用，
    改动展示格式不会影响解析。
    """
    return f"{window['pid']} ({window['x']},{window['y']})"


def desktop_option2pid(option: str) -> str:
    """从下拉项文本中取回纯 PID；取不到时返回空串。

    界面回传的是展示文本，但落盘的 handle 必须是纯 PID（Handle 按数字消费），
    因此写入配置前统一在这里剥掉标题与坐标。用户手工填的纯数字原样通过。
    """
    if not option:
        return ''
    matched = re.match(r'\s*(\d+)', str(option))
    return matched.group(1) if matched else ''


class DesktopWindow:
    def find_desktop_window_by_pid(self, pid) -> int:
        """按 PID 查找桌面客户端窗口，返回窗口句柄；未找到抛 EmulatorNotRunningError。

        「找不到窗口」记 warning 而非 error：本方法的调用方多为探测存在性
        （desktop_window_exists 判断是否需要重拉、_desktop_wait_closed 确认已关闭），
        找不到是正常答案。真正的故障由上层在拿到 EmulatorNotRunningError 后判定，
        这样真故障不会被淹没在每轮任务收尾都出现的噪音里。

        同一 PID 下可能同时存在多个标题命中的顶层窗口（客户端多开共用同一标题；
        新版 MuMu 内核客户端启动期还带着启动器残留窗口），取客户区最大者即可。

        这里刻意**不设客户区面积下限**：窗口被最小化时客户区是 0x0，但客户端仍在
        运行，还原交给 desktop_window_restore_if_minimized。用面积下限去宣布「未运行」
        会把这个正常挂着的客户端判成掉线 → 触发误重拉并把配置 handle 覆盖成新实例
        （真机实测的循环就是这么起来的），而 BitBlt 截图前本来就会先把窗口还原。
        """
        try:
            pid_int = int(str(pid))
        except (TypeError, ValueError):
            logger.error(f'Invalid desktop PID: {pid}')
            raise EmulatorNotRunningError(f'Invalid desktop client PID: {pid}')

        def enum_cb(hwnd, param):
            param.append(hwnd)
            return True

        windows = []
        EnumWindows(enum_cb, windows)
        matches = []
        for hwnd in windows:
            if GetWindowText(hwnd) in DESKTOP_WINDOW_TITLES:
                _, win_pid = GetWindowThreadProcessId(hwnd)
                if win_pid == pid_int:
                    matches.append(hwnd)
        # 同 PID 的多个候选里取客户区最大者：正常渲染窗口面积最大，启动器残留/
        # 最小化窗口（客户区 0x0）会排在后面。读不到客户区的（枚举与取值之间被销毁）
        # 直接跳过，全部读不到才算未找到
        best, best_area = 0, -1
        for hwnd in matches:
            try:
                cl, ct, cr, cb = GetClientRect(hwnd)
                area = (cr - cl) * (cb - ct)
            except Exception:
                continue
            if area > best_area:
                best, best_area = hwnd, area
        if best:
            return best
        logger.warning(f'Desktop client window not found, PID={pid}')
        raise EmulatorNotRunningError(f'Desktop client window not found, PID={pid}')

    def _desktop_best_window(self, pid, fallback: int = 0) -> int:
        """取指定 PID 下客户区最大的候选窗口；查不到时回退 fallback。

        用于自动启动完成时的句柄确定：同一 PID 可能既带启动器残留窗口又带真渲染窗口，
        取客户区最大者才不会把截图绑到残壳上。
        """
        try:
            return self.find_desktop_window_by_pid(pid)
        except EmulatorNotRunningError:
            return fallback

    def desktop_pid(self):
        """返回当前桌面客户端 PID（int）；取不到返回 None。

        优先用实例 root_handle（运行时自动启动绑定后的新 PID），未设置时回退配置里的
        handle。本会话的 PID 判断必须以实例状态为准，否则重新拉起后会误判。
        """
        pid = getattr(self, 'root_handle', None) or self.config.script.device.handle
        try:
            return int(str(pid))
        except (TypeError, ValueError):
            return None

    def find_desktop_login_popup(self) -> int:
        """按 PID + 类名查找 MPay 账号登录弹窗，返回句柄；没有则返回 0。

        弹窗与游戏主窗口同 PID 但是独立顶层窗口（owner 为主窗口，非子窗口），
        没有子控件可枚举，只能按窗口类名定位。
        按 PID 过滤保证多开时各实例只处理自己客户端的弹窗。

        主窗口 BitBlt 是否包含这个 owner 窗口受桌面合成状态影响，同一个弹窗可能在
        不同错误截图中出现或消失，所以登录状态不能依赖截图判断。
        改按「HWND 是否仍存活」判断而不再过滤 IsWindowVisible：真机验证过已登录的
        客户端全系统枚举不到任何 MPAY_LOGIN 顶层窗口，说明客户端确认弹窗后是销毁它、
        而非隐藏。因此 HWND 存活即代表尚未登录。
        """
        pid_int = self.desktop_pid()
        if pid_int is None:
            return 0

        def enum_cb(hwnd, param):
            param.append(hwnd)
            return True

        windows = []
        EnumWindows(enum_cb, windows)
        for hwnd in windows:
            try:
                if GetClassName(hwnd) != DESKTOP_LOGIN_POPUP_CLASS:
                    continue
                if GetWindowThreadProcessId(hwnd)[1] == pid_int:
                    return hwnd
            except Exception:
                # 窗口在枚举与取属性之间被关闭，跳过即可
                continue
        return 0

    def desktop_confirm_login_popup(self, wait: float = 15.0) -> bool:
        """向 MPay 登录弹窗发送回车，并确认对应 HWND 已真实消失。

        弹窗是 DirectUI 独立顶层窗口，"进入游戏"只是绘制出来的像素、没有真实控件，
        实测后台鼠标消息（WM_MOUSEMOVE/LBUTTONDOWN/LBUTTONUP，Post 与 Send 都试过）
        完全无响应；同步与异步回车在无前台焦点时均可触发默认按钮。因此这里只发回车，
        并在 wait 秒内轮询确认弹窗 HWND 真的消失。

        返回 True 表示弹窗确实已关闭；False 表示没有弹窗，或超时后弹窗仍然存活。
        """
        if not self.find_desktop_login_popup():
            return False
        logger.info('Desktop MPay login popup found, press Enter to enter game')
        deadline = time.time() + wait
        while time.time() < deadline:
            hwnd = self.find_desktop_login_popup()
            if not hwnd:
                logger.info('Desktop MPay login popup confirmed closed')
                return True
            self._desktop_send_enter(hwnd)
            time.sleep(1)
        logger.warning(f'Desktop MPay login popup still present after {wait}s, Enter had no effect')
        return False

    def desktop_window_exists(self) -> bool:
        """桌面模式：目标 PID 对应窗口仍存在即视为客户端运行中。

        只判「标题命中的顶层窗口在不在」，不看客户区尺寸——窗口被最小化或被遮挡时
        客户端仍在运行，截图方法会先把窗口还原回来再取帧。

        优先用实例 root_handle（运行时自动启动绑定后的新 PID），未设置时回退配置里的
        handle。本会话的窗口存在性判断必须以实例状态为准，否则重新拉起后会误判为未运行。
        """
        pid = getattr(self, 'root_handle', None) or self.config.script.device.handle
        try:
            self.find_desktop_window_by_pid(pid)
            return True
        except EmulatorNotRunningError:
            return False

    def _desktop_wait_window_ready(self, pid, wait: float = DESKTOP_WINDOW_READY_WAIT) -> bool:
        """在 wait 秒内等待指定 PID 的客户端窗口出现；超时返回 False。

        用于「进程还活着、窗口暂时不可见」的空窗期。这段时间只能等，不能重新启动
        客户端：真正在跑的那个实例会变成多开或被顶掉，配置里的 handle 也会被新实例
        覆盖，从此再也绑不回原来的客户端。
        """
        deadline = time.time() + wait
        while True:
            try:
                self.find_desktop_window_by_pid(pid)
                return True
            except EmulatorNotRunningError:
                pass
            if time.time() >= deadline:
                logger.error(f'Desktop client process alive but window not ready in {wait}s, PID={pid}')
                return False
            time.sleep(DESKTOP_WINDOW_READY_POLL_INTERVAL)

    def desktop_client_offset(self) -> tuple:
        """返回客户区在窗口 DC 内的偏移 (x, y)，用于 BitBlt 扣除标题栏/边框。"""
        with dpi_awareness():
            window_rect = GetWindowRect(self.screenshot_handle_num)
            client_origin = ClientToScreen(self.screenshot_handle_num, (0, 0))
            return client_origin[0] - window_rect[0], client_origin[1] - window_rect[1]

    def desktop_client_size(self) -> tuple:
        """返回桌面客户端窗口客户区的物理像素尺寸 (width, height)。"""
        with dpi_awareness():
            rect = GetClientRect(self.screenshot_handle_num)
            return rect[2] - rect[0], rect[3] - rect[1]

    def desktop_client_size_virtual(self) -> tuple:
        """返回客户区在 DPI 虚拟化空间下的尺寸 (width, height)。

        OAS 进程未声明 DPI 感知，PostMessage 的 lParam 会被系统按该空间解释，
        因此后台输入的坐标必须换算到这里，而不是截图所用的物理空间。
        """
        rect = GetClientRect(self.screenshot_handle_num)
        return rect[2] - rect[0], rect[3] - rect[1]

    def _desktop_client_size(self, hwnd):
        """读窗口客户区物理尺寸，句柄已失效返回 None。

        客户端从登录界面切到游戏主窗口时会销毁重建渲染窗口，因此调整窗口期间的任何
        一次 Win32 调用都可能撞上失效句柄。GetClientRect 对废句柄抛
        (1400, '无效的窗口句柄')，不接住会直接崩掉整个脚本进程。
        """
        if not IsWindow(hwnd):
            return None
        try:
            rect = GetClientRect(hwnd)
        except Exception as e:
            logger.warning(f'GetClientRect failed (hwnd={hwnd}): {e}')
            return None
        return rect[2] - rect[0], rect[3] - rect[1]

    def _desktop_clear_handle_cache(self) -> None:
        """失效截图相关 cached_property，使其按当前 root_handle_num 重新求值。

        桌面模式下 screenshot_handle_num 直接返回 root_handle_num，但它是
        cached_property：客户端重开后 root_handle_num 已换成新 hwnd，缓存仍指向
        旧句柄，截图时 GetClientRect 会拿废句柄抛 (1400)。
        """
        for prop in ('screenshot_handle_num', 'screenshot_size'):
            if prop in self.__dict__:
                del_cached_property(self, prop)

    def _desktop_rebind_window(self) -> bool:
        """按 PID 重新查找客户端窗口并绑定新 hwnd，返回是否绑定成功。

        用于两类句柄刷新：窗口重建（登录界面切游戏主窗口）后更换句柄，以及同一 PID
        下换到客户区更大的那个候选窗口。进程还活着，不需要重拉客户端。
        """
        try:
            hwnd = self.find_desktop_window_by_pid(self.root_handle)
        except EmulatorNotRunningError:
            return False
        if hwnd != self.root_handle_num:
            logger.info(f'Desktop window handle changed, rebind hwnd {self.root_handle_num} -> {hwnd}')
            self.root_handle_num = hwnd
            self._desktop_clear_handle_cache()
        return True

    def desktop_window_set_size(self, width: int = 1280, height: int = 720) -> bool:
        """桌面模式：检测窗口客户区尺寸，非目标大小时用 SetWindowPos 调整到 width×height。

        窗口位置保持不变；返回是否执行了调整。全过程在 DPI 感知上下文内完成，
        GetClientRect/SetWindowPos 处理的都是物理像素，因此目标尺寸无需按缩放比换算，
        调整后客户区物理尺寸恰为 width×height，游戏画面与资产 1:1 对应。

        客户端确认登录弹窗后会销毁登录界面、重建游戏主窗口，调整过程中旧 hwnd 随时可能
        失效。此时不抛异常也不重拉客户端（进程还活着），而是按 PID 重新绑定重建后的
        窗口再试，最多 DESKTOP_RESIZE_ATTEMPTS 轮。
        """
        if not getattr(self, 'is_desktop_window', False):
            return False
        for attempt in range(1, DESKTOP_RESIZE_ATTEMPTS + 1):
            result = self._desktop_try_set_size(width, height)
            if result is not None:
                return result
            if attempt >= DESKTOP_RESIZE_ATTEMPTS:
                break
            logger.info(f'Desktop window invalid, rebind and retry resize '
                        f'({attempt}/{DESKTOP_RESIZE_ATTEMPTS})')
            time.sleep(DESKTOP_RESIZE_RETRY_INTERVAL)
            self._desktop_rebind_window()
        logger.warning(f'Desktop window resize gave up after {DESKTOP_RESIZE_ATTEMPTS} attempts, '
                       f'window kept invalid')
        return False

    def _desktop_try_set_size(self, width: int, height: int):
        """单轮尝试调整窗口尺寸。

        返回 True/False 表示本轮已得出结论（是否执行了调整）；返回 None 表示句柄失效，
        需由调用方重新绑定窗口后再试。三态的意义在于把「尺寸本来就对」（False）和
        「窗口正在重建」（None）区分开，否则前者会白等重试。
        """
        hwnd = self.root_handle_num
        if not hwnd or not IsWindow(hwnd):
            logger.warning(f'Desktop window handle invalid (hwnd={hwnd})')
            return None
        with dpi_awareness():
            size = self._desktop_client_size(hwnd)
            if size is None:
                logger.warning(f'Desktop window vanished before resize (hwnd={hwnd})')
                return None
            client_w, client_h = size
            logger.info(f'Desktop client size: {client_w}x{client_h} (physical), target {width}x{height}')
            if client_w == width and client_h == height:
                logger.info('Desktop client size already matches target')
                return False
            # 用 AdjustWindowRectEx 精确计算含标题栏/边框的窗口总尺寸
            style = GetWindowLong(hwnd, GWL_STYLE)
            ex_style = GetWindowLong(hwnd, GWL_EXSTYLE)
            total_w, total_h = _window_total_size(width, height, style, ex_style)
            logger.info(f'Resize desktop window to {total_w}x{total_h} to get client {width}x{height}')
            try:
                SetWindowPos(hwnd, HWND_TOP, 0, 0, total_w, total_h, SWP_NOMOVE | SWP_SHOWWINDOW)
            except Exception as e:
                # 拒绝访问通常是目标窗口权限更高（游戏以管理员运行）或客户端锁定窗口大小
                logger.error(f'SetWindowPos failed: {e}. '
                             f'请以管理员身份运行 OAS，或手动把游戏窗口设为 1280x720')
                return False
            # 校准：SetWindowPos 后的实际客户区可能与目标差几像素，按差值持续修正。
            # SetWindowPos 本身可能正好撞上客户端重建窗口，因此每轮都要重新确认句柄有效
            for _ in range(5):
                size = self._desktop_client_size(hwnd)
                if size is None:
                    logger.warning(f'Desktop window vanished during resize (hwnd={hwnd}), '
                                   f'client is rebuilding its window')
                    return None
                cw, ch = size
                if cw == width and ch == height:
                    return True
                total_w += width - cw
                total_h += height - ch
                logger.info(f'Calibrate desktop window to {total_w}x{total_h}, current client {cw}x{ch}')
                try:
                    SetWindowPos(hwnd, HWND_TOP, 0, 0, total_w, total_h, SWP_NOMOVE | SWP_SHOWWINDOW)
                except Exception as e:
                    logger.warning(f'SetWindowPos failed during calibration (hwnd={hwnd}): {e}')
                    return None
            return True

    # ------------------------------------------------------------------ 桌面客户端自动生命周期

    def desktop_resolve_install_root(self) -> str:
        """解析桌面客户端安装目录：优先 desktop_game_path 配置，其次自动发现。

        只认含 bin\\onmyoji.exe（或根目录 Launch.exe）的安装目录，找不到返回空串。
        仅桌面模式调用，不影响模拟器流程。
        """
        configured = getattr(self.config.script.device, 'desktop_game_path', '') or ''
        if configured:
            root = self._desktop_root_from_path(configured)
            if root is not None:
                return str(root)
            logger.warning(f'desktop_game_path 配置无效: {configured}，尝试自动发现')
        root = self._desktop_discover_install_root()
        return str(root) if root else ''

    @staticmethod
    def _desktop_root_from_path(value: str):
        """把用户填的路径归一化成安装目录；无效返回 None。"""
        path = Path(value).expanduser()
        if path.is_file():
            # 允许直接填 bin\\onmyoji.exe 或 Launch.exe 的完整路径
            if path.name.lower() == 'onmyoji.exe' and path.parent.name.lower() == 'bin':
                path = path.parent.parent
            elif path.name.lower() == 'launch.exe':
                path = path.parent
            else:
                path = path.parent
        candidate = path / 'bin' / 'onmyoji.exe'
        if candidate.is_file():
            return path.resolve()
        return None

    @staticmethod
    def _desktop_discover_install_root():
        """按 %ProgramFiles%\\Onmyoji 与注册表 Uninstall 的 InstallLocation 自动发现安装目录。"""
        for env in ('ProgramFiles', 'ProgramFiles(x86)'):
            raw = os.environ.get(env)
            if raw and (Path(raw) / 'Onmyoji' / 'bin' / 'onmyoji.exe').is_file():
                return (Path(raw) / 'Onmyoji').resolve()
        try:
            import winreg
            roots = (
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),
                (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
            )
            for hive, key_path in roots:
                try:
                    with winreg.OpenKey(hive, key_path) as parent:
                        for index in range(winreg.QueryInfoKey(parent)[0]):
                            try:
                                with winreg.OpenKey(parent, winreg.EnumKey(parent, index)) as child:
                                    display, _ = winreg.QueryValueEx(child, 'DisplayName')
                                    if '阴阳师' not in str(display) and 'Onmyoji' not in str(display):
                                        continue
                                    location, _ = winreg.QueryValueEx(child, 'InstallLocation')
                                    if location and (Path(location) / 'bin' / 'onmyoji.exe').is_file():
                                        return Path(location).resolve()
                            except OSError:
                                continue
                except OSError:
                    continue
        except Exception:
            pass
        return None

    @staticmethod
    def desktop_game_exe(root) -> str:
        """返回游戏可执行文件路径；找不到返回空串。

        顺序即优先级：必须优先游戏本体 bin/onmyoji.exe。
        Launch.exe 是登录器，它会再拉起 bin/onmyoji.exe，
        导致双开且 OAS 绑定到登录器 PID 上找不到游戏窗口。
        """
        root = Path(root)
        for name in ('bin/onmyoji.exe', 'Launch.exe'):
            exe = root / name
            if exe.is_file():
                return str(exe)
        return ''

    def launch_desktop_client(self, timeout: int = 90) -> bool:
        """自动启动桌面客户端并绑定新窗口的 PID/HWND，成功返回 True。

        单轮 = 启动 exe → 等新窗口出现并稳定 → 绑定其 PID/HWND。到此启动即完成；
        MPay 登录弹窗与进游戏属登录流程，由 Restart 的 app_handle_login 负责。
        timeout 内没等到窗口说明客户端起歪了（卡加载、崩在启动期等），强杀本轮进程后
        整轮重跑一次；第二轮仍失败则记 error 返回 False，由上层停下等人工，不无限重试。
        安装目录/exe 找不到属配置问题，重试无意义，直接返回 False。
        """
        root = self.desktop_resolve_install_root()
        if not root:
            logger.error('未找到阴阳师桌面客户端安装目录，请在 设置-Script-设备 中填写 desktop_game_path')
            return False
        exe = self.desktop_game_exe(root)
        if not exe:
            logger.error(f'未找到游戏程序（bin\\onmyoji.exe 或 Launch.exe）：{root}')
            return False

        for attempt in (1, 2):
            pids = self._desktop_launch_attempt(exe, root, timeout, attempt)
            if pids is None:
                # Popen 本身失败，重试也起不来
                return False
            bound_pid, spawned_pid = pids
            if bound_pid:
                # 启动成功也要记住本轮拉起的全部 PID：onmyoji.exe 是启动器，它会派生出
                # 真正的游戏窗口进程后自己继续存活（实测启动器 8932 派生窗口进程 6816，
                # 89 线程 42s CPU 却无窗口）。OAS 靠枚举窗口只绑到窗口进程，关闭时若只杀
                # 它，启动器就成了无主残留。这里留档，交给 desktop_stop_client 一并清理
                self._desktop_spawned_pids = set(spawned_pid)
                # 客户端已拉起，强制保持显示器常亮，防止电源超时关屏导致截图黑帧卡死
                desktop_keep_screen_on(True)
                return True
            if attempt == 1:
                # 只杀本轮确切启动的进程：绑定阶段就失败时 root_handle 仍是上一次的陈旧
                # PID，直接调 desktop_force_kill 会误杀（PID 可能已被系统复用）
                logger.warning('第 1 轮启动未就绪，清理本轮客户端后重试')
                self._desktop_kill_pids(spawned_pid)
        logger.error('桌面客户端连续 2 轮启动均未就绪，请检查客户端状态与机器负载')
        return False

    def _desktop_launch_attempt(self, exe: str, root: str, timeout: int, attempt: int):
        """启动客户端并绑定其窗口的单轮尝试。

        返回 (bound_pid, spawned_pid)：bound_pid 非 0 表示本轮成功；spawned_pid 是本轮
        Popen 出的进程与绑定到的窗口 PID 集合，供失败清理精确定位。Popen 失败返回 None。
        """
        before_pids = {w['pid'] for w in list_desktop_windows()}
        logger.info(f'自动启动桌面客户端（第 {attempt} 轮）: {exe}')
        spawned = set()
        try:
            proc = subprocess.Popen([exe], cwd=root,
                                    creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
            spawned.add(proc.pid)
        except Exception as e:
            logger.error(f'启动桌面客户端失败: {e}')
            return None

        deadline = time.time() + timeout
        stable_hwnd = 0
        stable_count = 0
        while time.time() < deadline:
            # 候选必须落在安装目录下的进程：客户端新旧版本窗口标题不同
            # （"阴阳师-网易游戏" / "阴阳师-MuMu模拟器专版"），启动等待期内任何
            # 匹配标题的新窗口都会成为候选，按 exe 归属收口，避免绑到别的进程
            candidates = [w for w in list_desktop_windows()
                          if w['pid'] not in before_pids
                          and _desktop_pid_under_root(w['pid'], root)]
            if candidates:
                candidate = candidates[0]
                if candidate['hwnd'] == stable_hwnd:
                    stable_count += 1
                else:
                    stable_hwnd = candidate['hwnd']
                    stable_count = 1
                if stable_count >= 2:
                    # 同一 PID 可能还带着启动器残留窗口（客户区极小），句柄统一取
                    # 客户区最大者，否则截图会绑到残壳上（BitBlt 取不到画面）
                    hwnd = self._desktop_best_window(candidate['pid'], candidate['hwnd'])
                    self.desktop_bind_pid(candidate['pid'], hwnd)
                    spawned.add(candidate['pid'])
                    logger.info(f'桌面客户端已自动启动并绑定 PID={candidate["pid"]}')
                    # 到这里启动就完成了：进程在跑、窗口句柄已绑定。
                    # MPay 登录弹窗与进游戏属于登录流程，由 Restart 的 app_handle_login
                    # 负责（登录循环每轮都复查弹窗，中途冒出来也能接住）。
                    return candidate['pid'], spawned
            time.sleep(1)
        logger.warning(f'桌面客户端进程已启动，但 {timeout} 秒内未识别到游戏窗口')
        return 0, spawned

    def _desktop_kill_pids(self, pids) -> None:
        """强杀指定 PID 集合（本轮启动失败的清理），逐个容错并验证真的退出。"""
        kernel32 = ctypes.windll.kernel32
        wait = self._desktop_close_wait_seconds()
        for pid in pids:
            try:
                pid_int = int(pid)
            except (TypeError, ValueError):
                continue
            for attempt in range(1, DESKTOP_KILL_ATTEMPTS + 1):
                # PROCESS_TERMINATE(0x0001)
                handle = kernel32.OpenProcess(0x0001, False, pid_int)
                if not handle:
                    # 进程已自行退出
                    break
                try:
                    kernel32.TerminateProcess(handle, 0)
                    logger.info(f'清理桌面客户端 PID={pid_int}')
                finally:
                    kernel32.CloseHandle(handle)
                # 杀完必须确认进程真的没了，被拒或正在退出都会让下一轮启动撞上残留
                if self._desktop_wait_pid_gone(pid_int, wait):
                    break
                logger.warning(f'桌面客户端 PID={pid_int} 强杀后仍存活，重试 '
                               f'({attempt}/{DESKTOP_KILL_ATTEMPTS})')
            else:
                logger.error(f'桌面客户端 PID={pid_int} 无法清理，可能需要手动结束进程')
        # 等窗口真的消失，避免残留窗口干扰下一轮的新窗口识别
        self._desktop_wait_closed(wait)

    def _desktop_wait_pid_gone(self, pid, wait: float) -> bool:
        """在 wait 秒内等待指定进程退出，返回是否已退出。"""
        deadline = time.time() + wait
        while True:
            if not self._desktop_pid_alive(pid):
                return True
            if time.time() >= deadline:
                return False
            time.sleep(DESKTOP_KILL_POLL_INTERVAL)

    def desktop_bind_pid(self, pid, hwnd=0) -> None:
        """把新 PID/HWND 绑定到实例，并尽量持久化到配置。"""
        self.root_handle = str(pid)
        if hwnd:
            self.root_handle_num = hwnd
        self.root_handle_title = DESKTOP_WINDOW_TITLES[0]
        self.is_desktop_window = True
        # 换了新 hwnd，截图句柄缓存必须同步失效，否则截图仍走上一个客户端的废句柄
        self._desktop_clear_handle_cache()
        # 新绑定的客户端刚启动，必然未登录，需先走 restart 登录流程
        self._desktop_login_done = False
        logger.info(f'Desktop client bound: PID={pid}, hwnd={hwnd}')
        try:
            self.config.script.device.handle = str(pid)
            self.config.save()
        except Exception as e:
            logger.warning(f'持久化桌面 PID 到配置失败: {e}')

    def _desktop_send_enter(self, hwnd) -> None:
        """向窗口发送回车键，用于确认 MPay 账号登录弹窗的默认按钮"进入游戏"。

        窗口可能在两条消息之间被销毁（回车已生效），此时忽略异常即可。
        """
        try:
            SendMessage(hwnd, WM_KEYDOWN, VK_RETURN, 0)
            SendMessage(hwnd, WM_KEYUP, VK_RETURN, 0)
        except Exception as e:
            logger.info(f'Send Enter to window {hwnd} failed (window may be closed): {e}')

    def _desktop_pid_alive(self, pid) -> bool:
        """进程是否还活着。无法判定时按「还活着」返回，宁可多等一轮也不误报已关闭。

        不能只看 OpenProcess 是否成功：进程已退出但仍有内核对象引用时 OpenProcess
        照样返回句柄，必须再用 GetExitCodeProcess 看退出码是否还是 STILL_ACTIVE(259)。
        窗口枚举不能替代这里——强杀被拒时窗口可能已销毁而进程还在，只验窗口会误判。
        """
        try:
            pid_int = int(str(pid))
        except (TypeError, ValueError):
            return False
        kernel32 = ctypes.windll.kernel32
        # PROCESS_QUERY_LIMITED_INFORMATION(0x1000)，比 QUERY_INFORMATION 权限要求更低
        handle = kernel32.OpenProcess(0x1000, False, pid_int)
        if not handle:
            # 打不开通常就是进程已退出；权限不足时也走这里，交给窗口检查兜底
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)

    def _desktop_wait_closed(self, wait: float) -> bool:
        """在 wait 秒内轮询等待桌面客户端窗口消失，返回是否已关闭。"""
        deadline = time.time() + wait
        while True:
            if not self.desktop_window_exists():
                return True
            if time.time() >= deadline:
                return False
            time.sleep(0.5)

    def _desktop_wait_released(self, pid, wait: float) -> bool:
        """在 wait 秒内等待客户端真正释放：窗口消失 **且** 进程退出。

        两个条件都要，缺一个都可能是假关闭：
        - 只验窗口：强杀被拒时窗口已销毁但进程还在，会漏掉残留进程
        - 只验进程：进程刚退出时窗口可能还在被系统回收，下一轮新窗口识别会撞上
        """
        deadline = time.time() + wait
        while True:
            if not self.desktop_window_exists() and not self._desktop_pid_alive(pid):
                return True
            if time.time() >= deadline:
                return False
            time.sleep(DESKTOP_KILL_POLL_INTERVAL)

    def desktop_stop_client(self) -> bool:
        """关闭桌面客户端：强杀进程并验证真的释放，返回是否确认关闭。

        客户端的退出确认框画在游戏窗口内部（不是独立顶层窗口），实测回车确认经常无效
        （进程不退出、主窗口只是被移到屏幕外），走 WM_CLOSE + 确认反而要多等几秒还未必
        关得掉，因此这里不发任何窗口消息，直接强杀进程。

        强杀不等于已关闭：TerminateProcess 可能因权限被拒（本机出现过 (5, '拒绝访问。')），
        进程也可能正在退出还没消失。所以每轮杀完都验证「窗口消失 且 进程退出」，没释放
        就再杀一轮，全部轮次用尽仍在则返回 False——调用方据此决定是重建还是交人工，
        绝不能发完 kill 指令就当成功返回。

        关闭后保留原 PID 在配置里；下次检测到该 PID 无效（客户端未运行）时，
        由启动/重拉链路重启客户端并把配置更新为重启后的新 PID。
        """
        # 客户端关闭后必然未登录，下次启动需重新走登录流程
        self._desktop_login_done = False
        # PID 要在清理句柄前取，后面的验证全靠它
        pid = getattr(self, 'root_handle', None) or self.config.script.device.handle
        hwnd = self.root_handle_num
        if (not hwnd or not IsWindow(hwnd)) and not self._desktop_pid_alive(pid):
            logger.info('Desktop client not running, skip stop')
            # 客户端已不在，解除强制亮屏，允许系统恢复正常的显示器电源管理
            desktop_keep_screen_on(False)
            self._reset_desktop_handle_state()
            # 窗口进程已没了也要收启动器：它无窗口，只看窗口永远发现不了
            self._desktop_kill_spawned_leftovers(pid)
            return True

        wait = self._desktop_close_wait_seconds()
        released = False
        for attempt in range(1, DESKTOP_KILL_ATTEMPTS + 1):
            logger.info(f'Stopping desktop client: force kill '
                        f'({attempt}/{DESKTOP_KILL_ATTEMPTS}, PID={pid})')
            self.desktop_force_kill()
            if self._desktop_wait_released(pid, wait):
                logger.info(f'Desktop client released (PID={pid})')
                # 客户端已确认关闭，解除强制亮屏，允许系统恢复正常的显示器电源管理
                desktop_keep_screen_on(False)
                released = True
                break
            logger.warning(f'Desktop client PID={pid} still present after {wait}s, retry kill')
        if not released:
            # 到这里客户端确实没关掉：句柄状态照常清零（它已不可信），但把失败如实报出去
            logger.error(f'Desktop client PID={pid} not released after '
                         f'{DESKTOP_KILL_ATTEMPTS} force kill attempts, manual cleanup needed')
        self._reset_desktop_handle_state()
        # 无论窗口进程是否关掉，本轮自己拉起的启动器都要一并收掉
        leftovers_cleared = self._desktop_kill_spawned_leftovers(pid)
        return released and leftovers_cleared

    def _desktop_kill_spawned_leftovers(self, bound_pid) -> bool:
        """清理本次自己拉起、但没被绑定的客户端进程，返回是否已全部清掉。

        onmyoji.exe 是启动器：Popen 起来后它派生真正的游戏窗口进程，自己继续存活且
        没有窗口（实测启动器 89 线程、42s CPU、主窗口句柄为 0）。OAS 靠枚举游戏窗口
        绑定，只会绑到窗口进程，关闭时若只杀它，启动器就成了无主残留——既占内存，
        也让下一轮启动的窗口识别多一个干扰源。这些 PID 由 launch_desktop_client
        在启动成功时留档到 _desktop_spawned_pids。
        """
        spawned = getattr(self, '_desktop_spawned_pids', None)
        if not spawned:
            return True
        try:
            bound = int(str(bound_pid))
        except (TypeError, ValueError):
            bound = None
        # 已绑定的那个由主流程负责，这里只收剩下的
        leftovers = {p for p in spawned if p != bound and self._desktop_pid_alive(p)}
        self._desktop_spawned_pids = set()
        if not leftovers:
            return True
        logger.info(f'清理本次启动残留的客户端进程（启动器）: {sorted(leftovers)}')
        self._desktop_kill_pids(leftovers)
        still = {p for p in leftovers if self._desktop_pid_alive(p)}
        if still:
            logger.error(f'客户端启动器进程无法清理: {sorted(still)}，可能需要手动结束')
            return False
        return True

    def _reset_desktop_handle_state(self) -> None:
        """清零桌面窗口句柄与截图句柄缓存。

        进程已杀，hwnd 随窗口销毁立即失效。必须清零，否则后续在同一个 device 对象
        生命周期内被唤醒的任务（如配置变更触发的即时调度）会跳过 Handle.__init__，
        直接拿这个废句柄去 GetClientRect，抛 (1400, '无效的窗口句柄') 搞崩整个进程。
        """
        self.root_handle_num = 0
        # 截图句柄缓存指向的也是刚被销毁的窗口，一并失效
        self._desktop_clear_handle_cache()

    def _desktop_close_wait_seconds(self) -> int:
        """关闭游戏等待时长（秒），读 config.script.optimization.close_game_wait_duration。"""
        try:
            t = self.config.script.optimization.close_game_wait_duration
            return t.hour * 3600 + t.minute * 60 + t.second
        except Exception:
            return 10

    def desktop_force_kill(self) -> None:
        """强杀桌面客户端进程（WM_CLOSE 超时未退出的兜底）。"""
        pid = getattr(self, 'root_handle', None) or self.config.script.device.handle
        try:
            pid_int = int(str(pid))
        except (TypeError, ValueError):
            logger.error(f'Invalid desktop PID: {pid}, skip force kill')
            return
        kernel32 = ctypes.windll.kernel32
        # PROCESS_TERMINATE(0x0001)
        handle = kernel32.OpenProcess(0x0001, False, pid_int)
        if not handle:
            # 进程已自行退出
            return
        try:
            kernel32.TerminateProcess(handle, 0)
            logger.info(f'Desktop client PID={pid_int} force terminated')
        finally:
            kernel32.CloseHandle(handle)

    def desktop_window_restore_if_minimized(self, wait: float = 3.0) -> bool:
        """桌面窗口被最小化（用户误操作）时还原并等待客户区恢复，返回是否发生过还原。

        还原成功后若客户区尺寸偏离目标（1280x720），一并重校准，保证识别 1:1。
        """
        if not getattr(self, 'is_desktop_window', False):
            return False
        hwnd = self.root_handle_num
        if not hwnd or not IsIconic(hwnd):
            return False
        logger.warning('Desktop client window is minimized, restoring')
        ShowWindow(hwnd, SW_RESTORE)
        deadline = time.time() + wait
        restored = False
        while time.time() < deadline:
            with dpi_awareness():
                rect = GetClientRect(hwnd)
            if (rect[2] - rect[0]) > 0 and (rect[3] - rect[1]) > 0:
                restored = True
                break
            time.sleep(0.2)
        if restored:
            self.desktop_window_set_size()
        return restored
