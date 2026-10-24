import re
from functools import wraps

import cv2
import numpy as np
import time
from adbutils.errors import AdbError
from lxml import etree

from module.base.decorator import Config
from module.device.connection import Connection
from module.device.method.minitouch import smooth_path
from module.device.method.utils import (RETRY_TRIES, retry_sleep, remove_prefix, handle_adb_error,
                                        ImageTruncated, PackageNotInstalled)
from module.exception import RequestHumanTakeover, ScriptError, EmulatorNotRunningError
from module.logger import logger


def retry(func):
    @wraps(func)
    def retry_wrapper(self, *args, **kwargs):
        """
        Args:
            self (Adb):
        """
        init = None
        for _ in range(RETRY_TRIES):
            try:
                if callable(init):
                    retry_sleep(_)
                    init()
                return func(self, *args, **kwargs)
            # Can't handle
            except RequestHumanTakeover:
                break
            # Emulator not running, try to restart it
            except EmulatorNotRunningError:
                logger.error('Emulator not running, attempting to restart')
                if hasattr(self, 'emulator_start'):
                    self.emulator_start()

                def init():
                    self.adb_reconnect()
            # When adb server was killed
            except ConnectionResetError as e:
                logger.error(e)

                def init():
                    self.adb_reconnect()
            # AdbError
            except AdbError as e:
                if handle_adb_error(e):
                    def init():
                        self.adb_reconnect()
                else:
                    break
            # Package not installed
            except PackageNotInstalled as e:
                logger.error(e)

                def init():
                    self.detect_package()
            # ImageTruncated
            except ImageTruncated as e:
                logger.error(e)

                def init():
                    pass
            # Unknown
            except Exception as e:
                logger.exception(e)

                def init():
                    pass

        logger.critical(f'Retry {func.__name__}() failed')
        raise RequestHumanTakeover

    return retry_wrapper


def load_screencap(data):
    """
    Args:
        data: Raw data from `screencap`

    Returns:
        np.ndarray:
    """
    # Load data
    header = np.frombuffer(data[0:12], dtype=np.uint32)
    channel = 4  # screencap sends an RGBA image
    width, height, _ = header  # Usually to be 1280, 720, 1

    image = np.frombuffer(data, dtype=np.uint8)
    if image is None:
        raise ImageTruncated('Empty image after reading from buffer')

    try:
        image = image[-int(width * height * channel):].reshape(height, width, channel)
    except ValueError as e:
        # ValueError: cannot reshape array of size 0 into shape (720,1280,4)
        raise ImageTruncated(str(e))

    image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    if image is None:
        raise ImageTruncated('Empty image after cv2.cvtColor')

    return image


class Adb(Connection):
    __screenshot_method = [0, 1, 2]
    __screenshot_method_fixed = [0, 1, 2]

    @staticmethod
    def __load_screenshot(screenshot, method):
        if method == 0:
            pass
        elif method == 1:
            screenshot = screenshot.replace(b'\r\n', b'\n')
        elif method == 2:
            screenshot = screenshot.replace(b'\r\r\n', b'\n')
        else:
            raise ScriptError(f'Unknown method to load screenshots: {method}')

        # fix compatibility issues for adb screencap decode problem when the data is from vmos pro
        # When use adb screencap for a screenshot from vmos pro, there would be a header more than that from emulator
        # which would cause image decode problem. So i check and remove the header there.
        screenshot = remove_prefix(screenshot, b'long long=8 fun*=10\n')

        image = np.frombuffer(screenshot, np.uint8)
        if image is None:
            raise ImageTruncated('Empty image after reading from buffer')

        image = cv2.imdecode(image, cv2.IMREAD_COLOR)
        if image is None:
            raise ImageTruncated('Empty image after cv2.imdecode')

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        if image is None:
            raise ImageTruncated('Empty image after cv2.cvtColor')

        return image

    def __process_screenshot(self, screenshot):
        for method in self.__screenshot_method_fixed:
            try:
                result = self.__load_screenshot(screenshot, method=method)
                self.__screenshot_method_fixed = [method] + self.__screenshot_method
                return result
            except (OSError, ImageTruncated):
                continue

        self.__screenshot_method_fixed = self.__screenshot_method
        if len(screenshot) < 500:
            logger.warning(f'Unexpected screenshot: {screenshot}')
        raise OSError(f'cannot load screenshot')

    # MuMu 6.0 (Android 15 engine) runs every app on its own virtual display
    # (mumuscreenNNN), while `screencap` and `input` default to display 0 (the
    # desktop). Detect the display the game is running on and target it.
    _mumu_display_ids_cache = None
    _mumu_display_ids_retry_at = 0.0
    _mumu_display_ids_generation = 0
    _MUMU_DISPLAY_RETRY_SEC = 20
    _MUMU_DISPLAY_TIMEOUT = 3

    def _reset_mumu_display_ids(self):
        self._mumu_display_ids_cache = None
        self._mumu_display_ids_retry_at = 0.0
        self._mumu_display_ids_generation += 1

    def _mumu_display_ids(self):
        """
        Returns:
            tuple[int, str] | None:
                (display id for `input -d`, long display id for `screencap -d`)
                or None if not applicable (single-display devices, or the game
                is not running yet).
        """
        if self._mumu_display_ids_cache is not None:
            return self._mumu_display_ids_cache
        # A provisional miss (dumpsys broken, or the game display not up yet) is
        # retried on the next call; only the definitive "no virtual display at
        # all" result is remembered, and only for a short window, so a plain
        # single-display device does not pay a `dumpsys` call per click.
        now = time.monotonic()
        if now < self._mumu_display_ids_retry_at:
            return None
        generation = self._mumu_display_ids_generation
        try:
            # 1) Which display is the game on? Skip display 0, the desktop. The
            #    game's display is the one holding a window of our package; a
            #    system dialog on top of it takes the focus away from the
            #    package, so a non-launcher focus is the fallback.
            out = self.adb_shell(['dumpsys', 'window', 'displays'], timeout=self._MUMU_DISPLAY_TIMEOUT)
            display_id = None
            fallback = None
            virtual_display = False
            current = None
            for line in out.splitlines():
                m = re.search(r'Display: mDisplayId=(\d+)', line)
                if m:
                    current = int(m.group(1))
                    virtual_display = virtual_display or current != 0
                    continue
                if not current:
                    continue
                if self.package and self.package in line:
                    display_id = current
                    break
                if fallback is None and 'mFocusedApp=ActivityRecord' in line and 'launcher' not in line.lower():
                    fallback = current
            if display_id is None:
                display_id = fallback
            if display_id is None:
                if not virtual_display:
                    # Plain single-display device: do not probe on every call.
                    self._mumu_display_ids_retry_at = now + self._MUMU_DISPLAY_RETRY_SEC
                # Otherwise the game display is not up yet - retry next call.
                return None
            # 2) Display name, e.g. "mumuscreen002"
            name = None
            out = self.adb_shell(['dumpsys', 'display'], timeout=self._MUMU_DISPLAY_TIMEOUT)
            idx = out.find('mDisplayId=%d' % display_id)
            if idx >= 0:
                m = re.search(r'name=(mumuscreen\d+)', out[idx:idx + 6000])
                name = m.group(1) if m else None
            if name is None:
                return None
            # 3) SurfaceFlinger long display id for `screencap -d`
            long_id = None
            out = self.adb_shell(['dumpsys', 'SurfaceFlinger', '--display-id'], timeout=self._MUMU_DISPLAY_TIMEOUT)
            for line in out.splitlines():
                if 'displayName="%s"' % name in line:
                    m = re.search(r'Display (\d+)', line)
                    if m:
                        long_id = m.group(1)
                        break
            if long_id is None:
                return None
            if generation != self._mumu_display_ids_generation:
                # The app was restarted while the display was being probed.
                return None
            logger.info(f'MuMu multi-display: game on display {display_id} ({name}), screencap id {long_id}')
            self._mumu_display_ids_cache = (display_id, long_id)
            return self._mumu_display_ids_cache
        except Exception as e:
            logger.warning(f'Failed to detect MuMu multi-display setup: {e}')
            return None

    def _input_prefix(self):
        """
        Returns:
            list: `['input']` or `['input', '-d', '<display>']` for the game display.
        """
        cmd = ['input']
        ids = self._mumu_display_ids()
        if ids:
            cmd += ['-d', str(ids[0])]
        return cmd

    @retry
    @Config.when(DEVICE_OVER_HTTP=False)
    def screenshot_adb(self):
        cmd = ['screencap', '-p']
        ids = self._mumu_display_ids()
        if ids:
            cmd += ['-d', ids[1]]
        data = self.adb_shell(cmd, stream=True)
        if len(data) < 500:
            logger.warning(f'Unexpected screenshot: {data}')

        return self.__process_screenshot(data)

    @retry
    @Config.when(DEVICE_OVER_HTTP=True)
    def screenshot_adb(self):
        cmd = ['screencap']
        ids = self._mumu_display_ids()
        if ids:
            cmd += ['-d', ids[1]]
        data = self.adb_shell(cmd, stream=True)
        if len(data) < 500:
            logger.warning(f'Unexpected screenshot: {data}')

        return load_screencap(data)

    @retry
    def screenshot_adb_nc(self):
        cmd = ['screencap']
        ids = self._mumu_display_ids()
        if ids:
            cmd += ['-d', ids[1]]
        data = self.adb_shell_nc(cmd)
        if len(data) < 500:
            logger.warning(f'Unexpected screenshot: {data}')

        return load_screencap(data)

    @retry
    def click_adb(self, x, y):
        start = time.time()
        self.adb_shell(self._input_prefix() + ['tap', x, y])
        if time.time() - start <= 0.05:
            self.sleep(0.05)

    @retry
    def swipe_adb(self, p1, p2, duration=0.1):
        # 桌面客户端模式没有 adb 设备，滑动改走窗口消息路径（不影响模拟器流程）
        if getattr(self, 'is_desktop', False):
            return self.swipe_window_message(p1, p2)
        duration = int(duration * 1000)
        self.adb_shell(self._input_prefix() + ['swipe', *p1, *p2, duration])

    def long_click_adb(self, x: float, y: float, duration: float):
        """

        :param x:
        :param y:
        :param duration: 单位是s
        :return:
        """
        if not 0 < duration < 3:
            duration = duration / 1000
        self.adb_shell(self._input_prefix() + ['swipe', x, y, x, y, int(duration*1000)])

    @retry
    def app_current_adb(self):
        """
        Copied from uiautomator2

        Returns:
            str: Package name.

        Raises:
            OSError

        For developer:
            Function reset_uiautomator need this function, so can't use jsonrpc here.
        """
        # Related issue: https://github.com/openatx/uiautomator2/issues/200
        # $ adb shell dumpsys window windows
        # Example output:
        #   mCurrentFocus=Window{41b37570 u0 com.incall.apps.launcher/com.incall.apps.launcher.Launcher}
        #   mFocusedApp=AppWindowToken{422df168 token=Token{422def98 ActivityRecord{422dee38 u0 com.example/.UI.play.PlayActivity t14}}}
        # Regexp
        #   r'mFocusedApp=.*ActivityRecord{\w+ \w+ (?P<package>.*)/(?P<activity>.*) .*'
        #   r'mCurrentFocus=Window{\w+ \w+ (?P<package>.*)/(?P<activity>.*)\}')
        _focusedRE = re.compile(
            r'mCurrentFocus=Window{.*\s+(?P<package>[^\s]+)/(?P<activity>[^\s]+)\}'
        )
        m = _focusedRE.search(self.adb_shell(['dumpsys', 'window', 'windows']))
        if m:
            return m.group('package')

        # try: adb shell dumpsys activity top
        _activityRE = re.compile(
            r'ACTIVITY (?P<package>[^\s]+)/(?P<activity>[^/\s]+) \w+ pid=(?P<pid>\d+)'
        )
        output = self.adb_shell(['dumpsys', 'activity', 'top'])
        ms = _activityRE.finditer(output)
        ret = None
        for m in ms:
            ret = m.group('package')
        if ret:  # get last result
            return ret
        raise OSError("Couldn't get focused app")

    @retry
    def app_start_adb(self, package_name=None, allow_failure=False):
        """
        Args:
            package_name (str):
            allow_failure (bool):

        Returns:
            bool: If success to start
        """
        if not package_name:
            package_name = self.package
        result = self.adb_shell([
            'monkey', '-p', package_name, '-c',
            'android.intent.category.LAUNCHER', '--pct-syskeys', '0', '1'
        ])
        if 'No activities found' in result:
            # ** No activities found to run, monkey aborted.
            if allow_failure:
                return False
            else:
                logger.error(result)
                raise PackageNotInstalled(package_name)
        elif 'inaccessible' in result:
            # /system/bin/sh: monkey: inaccessible or not found
            pass
        else:
            # Events injected: 1
            # ## Network stats: elapsed time=4ms (0ms mobile, 0ms wifi, 4ms not connected)
            return True

        logger.warning('Fallback to use am start')
        result = self.adb_shell(['dumpsys', 'package', package_name])
        res = re.search(r'android.intent.action.MAIN:\s+\w+ ([\w.\/]+) filter \w+\s+'
                        r'.*\s+Category: "android.intent.category.LAUNCHER"',
                        result)
        if res:
            activity_name = res.group(1)
            self.adb_shell(['am', 'start', '-a', 'android.intent.action.MAIN', '-c',
                            'android.intent.category.LAUNCHER', '-n', activity_name])
        elif 'com.netease.ntunisdk.base.deeplink.UniDeepLinkActivity' in result:
            activity_name = 'com.netease.ntunisdk.base.deeplink.UniDeepLinkActivity'
            result = self.adb_shell([
                'am', 'start', '-n',
                f'{package_name}/com.netease.ntunisdk.base.deeplink.UniDeepLinkActivity'
            ])
        else:
            if allow_failure:
                return False
            else:
                logger.error(result)
                raise PackageNotInstalled(package_name)
        self.adb_shell(['am', 'start', '-a', 'android.intent.action.MAIN', '-c',
                        'android.intent.category.LAUNCHER', '-n', activity_name])

    @retry
    def app_stop_adb(self, package_name=None):
        """ Stop one application: am force-stop"""
        if not package_name:
            package_name = self.package
        self.adb_shell(['am', 'force-stop', package_name])

    @retry
    def dump_hierarchy_adb(self, temp: str = '/data/local/tmp/hierarchy.xml') -> etree._Element:
        """
        Args:
            temp (str): Temp file store on emulator.

        Returns:
            etree._Element:
        """
        # Remove existing file
        # self.adb_shell(['rm', '/data/local/tmp/hierarchy.xml'])

        # Dump hierarchy
        for _ in range(2):
            response = self.adb_shell(['uiautomator', 'dump', '--compressed', temp])
            if 'hierchary' in response:
                # UI hierchary dumped to: /data/local/tmp/hierarchy.xml
                break
            else:
                # <None>
                # Must kill uiautomator2
                self.app_stop_adb('com.github.uiautomator')
                self.app_stop_adb('com.github.uiautomator.test')
                continue

        # Read from device
        content = b''
        for chunk in self.adb.sync.iter_content(temp):
            if chunk:
                content += chunk
            else:
                break

        # Parse with lxml
        hierarchy = etree.fromstring(content)
        return hierarchy

    def draw_adb(self, points: list, interval=0.01):
        """
        通过多个点画连续线段，模拟连续触摸绘制

        Args:
            points: 点的列表，格式为 [(x1, y1), (x2, y2), ...]
            interval: 移动间隔时间（秒）
        """
        if len(points) < 2:
            logger.warning('至少需要2个点来画线')
            return

        # 平滑路径
        smooth_points = smooth_path(points)

        start_point = smooth_points[0]

        # 按下起始点
        self.adb_shell(self._input_prefix() + ['motionevent', 'DOWN', str(start_point[0]), str(start_point[1])])

        # 移动到后续点
        for i, point in enumerate(smooth_points[1:], start=1):
            # 给点间隔
            time.sleep(interval)
            self.adb_shell(self._input_prefix() + ['motionevent', 'MOVE', str(point[0]), str(point[1])])

        # 抬起手指
        final_point = smooth_points[-1]
        self.adb_shell(self._input_prefix() + ['motionevent', 'UP', str(final_point[0]), str(final_point[1])])


if __name__ == "__main__":
    adb = Adb(config='oas1')
    # logger.info(adb.app_start_adb())
    cv2.imshow("iiii", adb.screenshot_adb_nc())
    cv2.waitKey(0)
