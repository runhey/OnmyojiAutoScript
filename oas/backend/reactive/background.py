from typing import Union

from trio import CancelScope, Event, Nursery, current_time, move_on_after


class BackgroundTask:
    """
    逻辑预期功能：
    1. 默认不运行：只有调用 trigger() 后才启动后台任务。
    2. 执行与循环：执行一次函数后，默认每隔 2 秒重新执行一次。
    3. 重置逻辑：如果在 2 秒等待期间再次调用 trigger()，立即中断等待并运行函数，随后重新开始 2 秒计时。
    4. 合并触发 (基于 Event 替换)：
        - 在 task 执行期间，任何 trigger() 都会作用于旧的 Event 对象。
        - task 执行完后，立即替换为新的 Event 对象。
        - 结果：执行期间的触发被完全丢弃，执行完后总是进入完整的 2s 等待。
    5. 停止功能 (stop)：停止当前的执行和计时，进入“空闲”状态，任务进程不退出，等待 trigger() 唤醒。
    6. 完全关闭 (shutdown)：
        - fully=False: 销毁后台任务，再次 trigger() 会重新创建任务。
        - fully=True: 永久禁用，无法再次启动。
    """

    def __init__(self):
        # 触发后每隔X秒重新执行一次，或者None表示不重新执行
        self._recurrence: "Union[int, float, None]" = 2
        self._drop_threshold = 0.01
        self._event = Event()
        self._shutdown_scope = None  # 整个后台循环的生命周期
        self._stop_scope = None  # 当前“执行-等待”周期的生命周期
        self._permanently_disabled = False  # 永久禁用标志

        # 记录上一次任务结束的时间戳
        self._last_finish_time = -10000

    @property
    def recurrence(self):
        return self._recurrence

    @recurrence.setter
    def recurrence(self, value):
        if value is None:
            self._recurrence = None
        else:
            if value < 0:
                value = 0
            if value < self._drop_threshold:
                value = self._drop_threshold
            self._recurrence = value

    @property
    def drop_threshold(self):
        return self._drop_threshold

    @drop_threshold.setter
    def drop_threshold(self, value):
        if value < 0:
            value = 0
        self._drop_threshold = value

    async def task_run(self):
        pass

    async def _task_loop(self):
        """核心后台循环"""
        try:
            # 使用 CancelScope 管理整个任务的生命周期
            with CancelScope() as self._shutdown_scope:
                while True:
                    # --- 阶段 1: 空闲状态 ---
                    # 阻塞直到收到第一个触发信号
                    await self._event.wait()

                    # --- 阶段 2: 运行状态 ---
                    # 使用内部作用域，以便被 stop() 函数中断并回到“阶段 1”
                    with CancelScope() as self._stop_scope:
                        while True:
                            await self.task_run()
                            self._last_finish_time = current_time()
                            # 执行期间如果有人 set 了之前的那个 event，由于我们后面不再 wait 它，
                            # 那些触发信号会随着旧对象一起被垃圾回收。
                            self._event = Event()

                            # --- 阶段 3: 等待期 ---
                            # 等待 2 秒。如果此期间 self._rx 收到信号，wait 会提前结束
                            # move_on_after 会在 2 秒后自动退出该上下文块
                            _recurrence = self._recurrence
                            if _recurrence is not None:
                                with move_on_after(_recurrence):
                                    await self._event.wait()
                            else:
                                await self._event.wait()
        finally:
            # 无论是因为 shutdown 还是异常，确保状态清理
            self._shutdown_scope = None
            self._stop_scope = None
            self._last_finish_time = -10000
            self._event = Event()

    def task_trigger(self, nursery: Nursery):
        """
        触发任务，触发之后默认每隔 2 秒重新执行一次。
        调用触发不一定会执行一次任务，以下情况本次触发会被丢弃：
        - 处于 drop_threshold 内，调用触发不生效
        - 已经有一个任务正在运行或者即将运行，在它完成前调用触发不生效
        """
        if self._permanently_disabled:
            return

        # 如果当前时间距离上一次结束太近，则直接丢弃该信号
        now = current_time()
        if now - self._last_finish_time < self._drop_threshold:
            return

        # 状态检查与自动启动
        if self._shutdown_scope is None:
            # 重新初始化通道，清除旧信号
            self._event = Event()
            # 占位防止 start_soon 尚未调度时多次启动
            self._shutdown_scope = "STARTING"
            nursery.start_soon(self._task_loop)

        # 发送触发信号
        self._event.set()

    def task_stop(self):
        """停止逻辑：中断运行状态，回到空闲等待"""
        if self._stop_scope:
            self._stop_scope.cancel()
        self._stop_scope = None

    def task_shutdown(self, fully=False):
        """关闭逻辑：完全销毁后台任务"""
        if fully:
            self._permanently_disabled = True
        if self._shutdown_scope and self._shutdown_scope != "STARTING":
            self._shutdown_scope.cancel()
        self._last_finish_time = -10000
        self._event = Event()
