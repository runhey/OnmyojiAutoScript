
from collections import deque
from datetime import datetime

# Patch pkg_resources before importing adbutils and uiautomator2
from module.device.pkg_resources import get_distribution
# Just avoid being removed by import optimization
_ = get_distribution

from module.device.env import IS_WINDOWS
from module.base.timer import Timer
from module.config.utils import get_server_next_update
from module.device.app_control import AppControl
from module.device.control import Control
from module.device.desktop_device import DesktopDevice
from module.device.platform2 import Platform
from module.device.screenshot import Screenshot
from module.exception import (GameNotRunningError,
                              GameStuckError,
                              GameTooManyClickError,
                              RequestHumanTakeover,
                              EmulatorNotRunningError)
from module.logger import logger


class Device(DesktopDevice, Platform, Screenshot, Control, AppControl):
    _screen_size_checked = False
    detect_record = set()
    click_record = deque(maxlen=15)
    stuck_timer = Timer(60, count=60).start()
    stuck_timer_long = Timer(300, count=300).start()
    stuck_long_wait_list = ['BATTLE_STATUS_S', 'PAUSE', 'LOGIN_CHECK', 'PREPARE_BEFORE_BATTLE']

    def __init__(self, *args, **kwargs):
        for trial in range(4):
            try:
                super().__init__(*args, **kwargs)
                break
            except EmulatorNotRunningError:
                # 桌面客户端没有模拟器可拉：确保客户端在，再重跑一次基类完成窗口绑定
                if self.is_desktop:
                    if trial >= 1 or not self._desktop_ensure_launched():
                        logger.critical('Desktop client not found and auto-launch failed, '
                                        'please start the game and bind PID first')
                        raise RequestHumanTakeover from None
                    continue
                if trial >= 3:
                    logger.critical('Failed to start emulator after 3 trial')
                    raise RequestHumanTakeover
                # Try to start emulator
                if self.emulator_instance is not None:
                    self.emulator_start()
                else:
                    logger.critical(
                        f'No emulator with serial "{self.config.Emulator_Serial}" found, '
                        f'please set a correct serial'
                    )
                    raise RequestHumanTakeover

        # 桌面客户端模式：无模拟器生命周期
        if self.is_desktop:
            self._init_desktop()
            return

        # Auto-fill emulator info
        if IS_WINDOWS and self.config.script.device.emulatorinfo_type == 'auto':
            _ = self.emulator_instance

        self.screenshot_interval_set()

        # Auto-select the fastest screenshot method
        if self.config.script.device.screenshot_method == 'auto':
            self.run_simple_screenshot_benchmark()

    def run_simple_screenshot_benchmark(self):
        """
        Perform a screenshot method benchmark, test 3 times on each method.
        The fastest one will be set into config.
        """
        logger.info('run_simple_screenshot_benchmark')
        # Check resolution first
        # self.resolution_check_uiautomator2()
        # Perform benchmark
        from module.daemon.benchmark import Benchmark
        bench = Benchmark(config=self.config, device=self)
        method = bench.run_simple_screenshot_benchmark()
        # Set
        self.config.script.device.screenshot_method = method
        self.config.save()

    def handle_night_commission(self, daily_trigger='21:00', threshold=30):
        """
        Args:
            daily_trigger (int): Time for commission refresh.
            threshold (int): Seconds around refresh time.

        Returns:
            bool: If handled.
        """
        update = get_server_next_update(daily_trigger=daily_trigger)
        now = datetime.now()
        diff = (update.timestamp() - now.timestamp()) % 86400
        if threshold < diff < 86400 - threshold:
            return False

        # if GET_MISSION.match(self.image, offset=True):
        #     logger.info('Night commission appear.')
        #     self.click(GET_MISSION)
        #     return True

        return False

    def screenshot(self):
        """
        Returns:
            np.ndarray:
        """
        self.stuck_record_check()

        # 桌面模式：窗口缺失说明客户端当前不可用（启动期未出窗口，或客户端崩了）。
        # 直接截图会抛 (1400, '无效的窗口句柄') 搞崩整个进程，必须先拦下；拉客户端
        # 是 Restart 的职责。最小化不算窗口缺失——BitBlt 截图前会先还原窗口。
        if self.is_desktop and not self.desktop_window_exists():
            raise GameNotRunningError('Desktop client window not found')

        try:
            super().screenshot()
        except RequestHumanTakeover as e:
            raise RequestHumanTakeover

        if self.handle_night_commission():
            super().screenshot()

        return self.image

    def release_during_wait(self):
        # Scrcpy server is still sending video stream,
        # stop it during wait
        # self.config.script.device.screenshot_method = 'scrcpy'
        if self.config.script.device.screenshot_method == 'scrcpy':
            self._scrcpy_server_stop()
        if self.config.Emulator_ScreenshotMethod == 'nemu_ipc':
            self.nemu_ipc_release()

    def stuck_record_add(self, button):
        """
        当你要设置这个时候检测为长时间的时候，你需要在这里添加
        如果取消后，需要在`stuck_record_clear`中清除
        :param button:
        :return:
        """
        self.detect_record.add(str(button))
        logger.info(f'Add stuck record: {button}')

    def stuck_record_clear(self):
        self.detect_record = set()
        self.stuck_timer.reset()
        self.stuck_timer_long.reset()

    def stuck_record_check(self):
        """
        Raises:
            GameStuckError:
        """
        reached = self.stuck_timer.reached()
        reached_long = self.stuck_timer_long.reached()

        if not reached:
            return False
        if not reached_long:
            for button in self.stuck_long_wait_list:
                if button in self.detect_record:
                    return False

        logger.warning('Wait too long')
        logger.warning(f'Waiting for {self.detect_record}')
        self.stuck_record_clear()

        if self.app_is_running():
            raise GameStuckError(f'Wait too long')
        else:
            raise GameNotRunningError('Game died')

    def handle_control_check(self, button):
        self.stuck_record_clear()
        self.click_record_add(button)
        self.click_record_check()

    def click_record_add(self, button):
        self.click_record.append(str(button))

    def click_record_clear(self):
        self.click_record.clear()

    def click_record_remove(self, button):
        """
        Remove a button from `click_record`

        Args:
            button (Button):

        Returns:
            int: Number of button removed
        """
        removed = 0
        for _ in range(self.click_record.maxlen):
            try:
                self.click_record.remove(str(button))
                removed += 1
            except ValueError:
                # Value not in queue
                break

        return removed

    def click_record_check(self):
        """
        Raises:
            GameTooManyClickError:
        """
        count = {}
        for key in self.click_record:
            count[key] = count.get(key, 0) + 1
        count = sorted(count.items(), key=lambda item: item[1], reverse=True)
        if count[0][1] >= 10:
            logger.warning(f'Too many click for a button: {count[0][0]}')
            logger.warning(f'History click: {[str(prev) for prev in self.click_record]}')
            self.click_record_clear()
            raise GameTooManyClickError(f'Too many click for a button: {count[0][0]}')
        if len(count) >= 2 and count[0][1] >= 6 and count[1][1] >= 6:
            logger.warning(f'Too many click between 2 buttons: {count[0][0]}, {count[1][0]}')
            logger.warning(f'History click: {[str(prev) for prev in self.click_record]}')
            self.click_record_clear()
            raise GameTooManyClickError(f'Too many click between 2 buttons: {count[0][0]}, {count[1][0]}')

    def disable_stuck_detection(self):
        """
        Disable stuck detection and its handler. Usually uses in semi auto and debugging.
        """
        logger.info('Disable stuck detection')

        def empty_function(*arg, **kwargs):
            return False

        self.click_record_check = empty_function
        self.stuck_record_check = empty_function

    def app_start(self):
        # 桌面模式：窗口缺失时自动启动客户端并绑定 PID（空闲关闭后由 Restart 重新拉起）
        if self.is_desktop:
            if not self._desktop_ensure_launched():
                logger.error('Desktop client not running and auto-launch failed, '
                             'please start the game manually or check desktop_game_path')
                raise GameNotRunningError('Desktop client auto-launch failed')
            # 这里必然早于 app_handle_login，且是拉起客户端的唯一入口：客户区没校准到
            # 1280x720 的话登录 OCR 与点击坐标全错。运行期重拉时 Device 对象是复用的，
            # _init_desktop 不会再跑，所以校准不能只挂在初始化路径上
            self.desktop_window_set_size()
            return
        if not self.config.script.error.handle_error:
            logger.critical('No app stop/start, because HandleError disabled')
            logger.critical('Please enable Alas.Error.HandleError or manually login to AzurLane')
            raise RequestHumanTakeover
        super().app_start()
        self.stuck_record_clear()
        self.click_record_clear()

    def app_stop(self):
        # 桌面模式：关闭客户端。desktop_stop_client 内部已做「窗口消失 且 进程退出」
        # 验证并多轮重杀，关不掉时它已记 ERROR，这里只把结论透出
        if self.is_desktop:
            if not self.desktop_stop_client():
                logger.warning('Desktop client not released, residual process may remain')
            return
        if not self.config.script.error.handle_error:
            logger.critical('No app stop/start, because HandleError disabled')
            logger.critical('Please enable Alas.Error.HandleError or manually login to AzurLane')
            raise RequestHumanTakeover
        super().app_stop()
        self.stuck_record_clear()
        self.click_record_clear()


if __name__ == "__main__":
    device = Device(config="oas1")
    # cv2.imshow("imgSrceen", device.screenshot())  # 显示
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
