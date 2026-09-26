# Python 3.11+ 内置 BaseExceptionGroup，OAS 是 3.14，直接用内置名
_BaseExceptionGroup = BaseExceptionGroup


class suppress_keyboard_interrupt:
    """
    一个类形式的上下文管理器，对 Traceback 绝对透明。

    1. 捕获主逻辑中的 KI (及其异常组)
    2. 执行 callback
    3. 捕获 callback 中的 KI (及其异常组)
    4. 对主逻辑异常透明，对 callback 异常非透明

    Examples:
        with suppress_keyboard_interrupt():
            trio.run(func)
    """

    def __init__(self, callback: "Optional[Callable]" = None):
        self.callback = callback

    def __enter__(self):
        return self

    def _run_callback(self):
        """执行回调，并递归处理其中的 KeyboardInterrupt 异常组"""
        # 注意：这里故意不写 __tracebackhide__ = True，
        # 因为如果回调函数报了非 KI 的错误，我们需要在 Traceback 中看到这一层。
        if not self.callback:
            return

        try:
            self.callback()
        except KeyboardInterrupt:
            # 静默处理回调中直接抛出的 KI
            pass
        except _BaseExceptionGroup as eg:
            # 处理回调中抛出的异常组（例如 callback 内部又开了 Nursery）
            matched, rest = eg.split(KeyboardInterrupt)
            if rest is not None:
                # 如果回调中除了 KI 还有别的错误，抛出来（非透明，会显示本层）
                raise rest
            # 如果全是 KI，静默处理

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 告诉 PyCharm/pytest 等工具隐藏此帧
        __tracebackhide__ = True

        if exc_type is None:
            return False

        # 1. 处理直接的 KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            self._run_callback()
            return True  # 返回 True 表示完全静默该异常，不继续向上抛出

        # 2. 处理 ExceptionGroup 中的 KeyboardInterrupt
        if issubclass(exc_type, _BaseExceptionGroup):
            # split 会分离出匹配到的部分和剩余部分
            matched, rest = exc_val.split(KeyboardInterrupt)

            if matched is not None:
                # 主逻辑发生了中断信号，执行清理回调
                self._run_callback()

                if rest is None:
                    # 主逻辑全是 KI，回调也处理完了，静默退出
                    return True
                else:
                    # 主逻辑中包含除了 KI 以外的错误，需要透明地抛出
                    # 使用 raise from None 斩断异常链，隐藏本层
                    raise rest from None

        # 3. 其他异常，返回 False 让其正常冒泡
        return False