import os
import signal
import subprocess
import sys
import threading
from typing import List, Optional

from oas.ext.env import OAS_ROOT
from oas.testing.timeout import AssertTimeout


class ManagedProcess:
    """
    管理的子进程，带实时输出收集功能

    特性：
    - 自动创建独立进程组（避免信号干扰）
    - 后台线程实时收集stdout
    - 缓存所有输出用于检查
    - 提供wait_for_output()等待特定输出出现
    - 支持上下文管理器

    Example:
        with ManagedProcess("supervisor_backends.py", "normal") as proc:
            # 等待启动成功消息
            proc.wait_for_output("startup successful", timeout=10)

            # 检查是否有错误
            assert not proc.has_output("ERROR")

            # 发送中断信号
            proc.send_interrupt()

            # 等待优雅关闭
            proc.wait_for_output("graceful shutdown", timeout=5)
    """

    def __init__(self, script_path: str, *args: str):
        """
        创建并启动管理的进程

        Args:
            script_path: 要执行的脚本路径
            *args: 传递给脚本的参数
        """
        self.script_path = script_path
        self.args = args
        self.process: Optional[subprocess.Popen] = None
        self.collector_thread: Optional[threading.Thread] = None
        self.output_buffer: List[str] = []
        self.output_lock = threading.Lock()
        self.stop_collecting = threading.Event()

        # 启动进程
        self._start_process()

        # 启动输出收集线程
        self._start_collector()

    def _start_process(self):
        """创建子进程，使用独立的进程组"""
        python = sys.executable
        cmd = [python, self.script_path] + list(self.args)

        # The child runs ``python <script>`` so only the script directory
        # lands on sys.path; the project root is not importable unless the
        # package is pip-installed. Inject the project root into PYTHONPATH
        # so child processes can always ``import alasio``.
        env = os.environ.copy()
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = OAS_ROOT + (os.pathsep + existing if existing else "")

        if sys.platform == "win32":
            # Windows: 创建新的进程组
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # 行缓冲
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                env=env
            )
        else:
            # Unix/Linux: 使用preexec_fn创建新的进程组
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # 行缓冲
                preexec_fn=os.setpgrp,
                env=env
            )

    def _start_collector(self):
        """启动后台线程收集stdout"""
        self.collector_thread = threading.Thread(
            target=self._collect_output,
            daemon=True,
            name=f"OutputCollector-{self.process.pid}"
        )
        self.collector_thread.start()

    def _collect_output(self):
        """后台线程：持续收集stdout并缓存"""
        try:
            while not self.stop_collecting.is_set():
                # 使用readline读取一行
                line = self.process.stdout.readline()
                print(line.rstrip())

                if not line:
                    # EOF - 进程已退出
                    break

                # 添加到缓冲区
                with self.output_lock:
                    self.output_buffer.append(line)

        except Exception as e:
            # 收集过程中出错（例如进程被强制终止）
            with self.output_lock:
                self.output_buffer.append(f"[OutputCollector Error: {e}]\n")

    def get_output(self) -> str:
        """
        获取所有收集到的输出

        Returns:
            所有输出的字符串
        """
        with self.output_lock:
            return ''.join(self.output_buffer)

    def has_output(self, text: str, case_sensitive: bool = True) -> bool:
        """
        检查缓冲区是否包含特定文本

        Args:
            text: 要查找的文本
            case_sensitive: 是否区分大小写

        Returns:
            True如果找到，False否则
        """
        output = self.get_output()

        if not case_sensitive:
            output = output.lower()
            text = text.lower()

        return text in output

    def wait_for_output(
            self,
            text: str,
            timeout: float = 10.0,
            case_sensitive: bool = True,
            interval: float = 0.01,
            count: int = 1
    ) -> bool:
        """
        等待特定文本在输出中出现至少 count 次

        Args:
            text: 要等待的文本
            timeout: 超时时间（秒）
            case_sensitive: 是否区分大小写
            interval: 检查间隔（秒）
            count: 需要出现的次数（用于按轮次同步，如反复重启的用例）

        Returns:
            True如果文本出现，False如果超时

        Raises:
            AssertionError: 如果超时且文本未出现足够次数
        """
        for _ in AssertTimeout(timeout, interval=interval):
            with _:
                output = self.get_output()
                if not case_sensitive:
                    output = output.lower()
                    text = text.lower()
                assert output.count(text) >= count, \
                    f"Timeout waiting for '{text}' x{count} in output"

        return True

    def send_command(self, command: str):
        """
        向子进程 stdin 写一行命令（supervisor 的命令通道）

        The supervisor handles command:stop itself and forwards every other
        command:* line to the backend process verbatim, so a test can drive a
        fake backend step by step (e.g. command:step:restart) at the moment it
        has observed the state it wants to check.

        Args:
            command: Command line, the trailing newline is added if missing

        Raises:
            RuntimeError: If the process has no stdin pipe
        """
        if self.process is None or self.process.stdin is None:
            raise RuntimeError('Process stdin is not available')
        line = command if command.endswith('\n') else command + '\n'
        self.process.stdin.write(line)
        self.process.stdin.flush()

    def wait_for_exit(self, timeout: float = 10.0) -> int:
        """
        等待进程退出

        Args:
            timeout: 超时时间（秒）

        Returns:
            进程退出码

        Raises:
            TimeoutError: 如果超时
        """
        try:
            returncode = self.process.wait(timeout=timeout)
            return returncode
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Process did not exit within {timeout} seconds")

    def is_alive(self) -> bool:
        """
        检查进程是否还在运行

        Returns:
            True如果进程还在运行，False否则
        """
        return self.process is not None and self.process.poll() is None

    def send_interrupt(self):
        """发送中断信号（SIGINT/CTRL_C）"""
        if not self.is_alive():
            return

        if sys.platform == "win32":
            self.process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            # Unix/Linux: 使用SIGINT
            self.process.send_signal(signal.SIGINT)

    def terminate(self):
        """终止进程（SIGTERM）"""
        if self.is_alive():
            self.process.terminate()

    def kill(self):
        """强制杀死进程（SIGKILL）"""
        if self.is_alive():
            self.process.kill()

    def close(self):
        """
        关闭进程和收集线程

        步骤：
        1. 停止输出收集
        2. 如果进程还在运行，先terminate，等待，再kill
        3. 等待收集线程结束
        """
        # 停止收集线程
        self.stop_collecting.set()

        # 确保进程被终止
        if self.is_alive():
            self.terminate()

            # 等待最多2秒
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # 强制杀死
                self.kill()
                self.process.wait()

        # 等待收集线程结束
        if self.collector_thread and self.collector_thread.is_alive():
            self.collector_thread.join(timeout=1)

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
        return False

    def __repr__(self):
        status = "alive" if self.is_alive() else "dead"
        pid = self.process.pid if self.process else "N/A"
        return f"<ManagedProcess pid={pid} status={status} script={self.script_path}>"
