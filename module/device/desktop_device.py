# This Python file uses the following encoding: utf-8
"""桌面客户端（serial='desktop'）在 Device 层的生命周期策略。

窗口/进程的实现细节在 module/device/method/desktop_impl.py 的 DesktopWindow，
这里只管「什么时候把客户端拉起来、什么时候算它在运行」。
"""
from module.logger import logger


class DesktopDevice:
    # 登录态：OAS 自动启动的客户端停在 MPay 登录页时为 False，登录流程成功后
    # 置 True，运行期发现弹窗置回 False。默认 True 表示假设已在游戏中。
    _desktop_login_done = True

    def _desktop_ensure_launched(self) -> bool:
        """确保客户端可用：进程已死才拉起，进程活着只等窗口就绪。

        判定顺序是关键——先看进程再看窗口。把「窗口不在」当成「客户端没在运行」
        会拉起多余实例，并把配置里的 handle 覆盖成新实例的 PID，从此再也绑不回
        原来那个。窗口被最小化不算没运行，截图方法会先还原再取帧。
        """
        pid = self.desktop_pid()
        if pid is None or not self._desktop_pid_alive(pid):
            return self.launch_desktop_client()
        if self.desktop_window_exists():
            return True
        return self._desktop_wait_window_ready(pid)

    def app_lost_login(self) -> bool:
        """客户端是否掉回了未登录态。

        MPay 登录窗存活时游戏画面上的一切页面标志都无效，发现即复位登录标记，
        使 app_is_running() 与任务前置检查能拦住后续流程。模拟器模式恒为 False。
        """
        if not self.is_desktop or not self.find_desktop_login_popup():
            return False
        logger.warning('Desktop MPay login popup present, client is not logged in')
        self.desktop_mark_logged_out()
        return True

    def desktop_mark_logged_in(self) -> None:
        """标记客户端已完成登录（Restart 的登录流程成功后调用）。"""
        self._desktop_login_done = True

    def desktop_mark_logged_out(self) -> None:
        """标记客户端处于未登录态。"""
        self._desktop_login_done = False

    def _init_desktop(self) -> None:
        """桌面客户端模式初始化：跳过模拟器健康检查/full_recovery。"""
        logger.info('Desktop client mode: skip emulator health check and full recovery')
        if self.config.script.device.screenshot_method == 'auto':
            self.config.script.device.screenshot_method = 'window_background'
        if self.config.script.device.control_method != 'window_message':
            logger.warning(
                f'Desktop mode requires control_method=window_message, '
                f'current={self.config.script.device.control_method}, overriding'
            )
            self.config.script.device.control_method = 'window_message'
        self.config.save()
        self.screenshot_interval_set()
        # 桌面客户端的渲染经过 DPI 缩放重采样，相对模板截图环境（模拟器原生
        # 1280x720）存在约 1px 的相位差；仓库里约 1/3 的模板 roi 与模板等宽，
        # matchTemplate 结果只剩 1 列、横向无法平移补偿，这点相位差就足以把
        # 「元素存在」判成「不存在」。这里统一外扩 2px 吸收之，模拟器模式保持 0。
        from module.atom.image import DESKTOP_ROI_MATCH_PAD, set_roi_match_padding
        set_roi_match_padding(DESKTOP_ROI_MATCH_PAD)
        # 客户区校准到 1280x720 保证识别 1:1。窗口存在性已由 __init__ 的
        # _desktop_ensure_launched 保证，运行期掉了由 Restart 负责重拉
        self.desktop_window_set_size()
