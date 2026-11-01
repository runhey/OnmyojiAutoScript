"""
The backend <-> worker bridge: the worker side of the worker pipe.

Ported from alasio/backend/worker/bridge.py. Deviations:

- the 41-line fake that stood here is removed. It declared only
  ``inited`` / ``mod_name`` / ``config_name`` / ``send_log`` /
  ``send_worker_state`` plus a ``_Job.acquire()`` no-op, to keep the import
  path in ``oas/logger/writer.py`` alive. The real port keeps every member
  the writer touches (see the caller-contract note below), so the fake's
  ``_Job`` class and its two ``_Job()`` returns are gone: ``send_log`` and
  ``send_worker_state`` now return the ``threading.Lock`` that ``send()``
  hands back, exactly like upstream (upstream lines 500-507);
- no trio usage in upstream, so nothing was rewritten to anyio. Upstream
  only names trio in the light-import header comment (upstream lines 1-9),
  which is kept verbatim as a comment;
- upstream line 72 lazily imports ``tests.backend.worker.worker_mods``. OAS
  keeps its tests under ``tests/oas/`` and has no worker test mods, so that
  target is MISSING and was neither invented nor rewritten: the branch is
  guarded by ``mod_name.startswith('WorkerTest')`` and is dead in OAS. The
  line is left byte-identical (upstream lines 64-85);
- the two commented-out ``# from alasio.logger import logger`` lines
  (upstream lines 387 and 446) are comments, not imports, and stay as-is;
- ``ruff format`` (pyproject: target-version py314, quote-style single) is
  applied on top of the verbatim body, so four ``except (A, B):`` became
  ``except A, B:`` (upstream lines 329, 360, 378, 442 -- PEP 758, valid on
  3.14), quoting is normalized to single quotes and a few long lines are
  wrapped. No logic changed.
- ``ruff check`` (the repo D rules) is clean: upstream's ``mod_entry``
  docstring lists its arguments with no descriptions at all and
  ``BackendBridge.init`` starts with a lowercase word, so those two docstrings
  got the arguments of the house style and a capitalized first word. They are
  the only docstring wording changed here.

Caller contract: ``oas/logger/writer.py:26-32`` and ``:40-41`` and
``oas/logger/logger.py:326, 354, 359-362`` construct ``BackendBridge()`` with
no arguments, read ``.inited: bool`` and ``.config_name: str``, and call
``.send_log(event)`` whose result they only ``.acquire()``. The upstream class
provides every one of them as-is, so no caller adaptation was needed (the real
``send_log`` returns the ``threading.Lock`` of ``send()``, a superset of the
fake's ``_Job``). ``mod_entry`` is the spawn target of
``oas/backend/worker/manager.py:651-659``, which passes the same positional
``(mod, config, child_conn[, project_root, mod_root, path_main])`` tuple as
upstream ``alasio/backend/worker/manager.py:569-580``: the upstream signature
is kept unchanged.
"""

# =============================================================================
# PROCESS BOUNDARY -- module-level imports must stay LIGHT.
#
# This module is imported by BOTH the backend process (worker.manager holds
# the spawn target here) and the worker process (pickle target
# deserialization). Module-level imports must stay light: no web framework
# (starlette / trio / hypercorn) and no backend business modules. Test-only
# imports (tests.backend.worker.worker_mods) must stay local.
# =============================================================================

import importlib
import os
import sys
import time
from threading import Event, Lock, Thread, get_ident, main_thread
from typing import Literal

from msgspec.msgpack import Decoder, Encoder

from oas.backend.worker.event import CommandEvent, ConfigEvent
from oas.backport.threading_ext import PreemptiveEvent
from oas.ext import env
from oas.ext.cache import cached_property
from oas.ext.path.calc import to_python_import
from oas.ext.singleton import Singleton
from oas.logger import logger

# Exit code of a worker that terminated itself because its backend is gone, so
# a postmortem can tell it apart from a scheduler crash and a graceful stop.
BACKEND_LOST_EXIT_CODE = 3

# Seconds to wait for an injected KeyboardInterrupt to unwind the scheduler
# before the worker process is terminated directly. A scheduler blocked in a
# native call (one long time.sleep, a socket read, an adb round trip) never sees
# the exception, it survives this wait and gets terminated.
BACKEND_LOST_KILL_WAIT_TIMEOUT = 0.5


def _exit_process(code):
    """
    Terminate this process immediately

    A function instead of a bare os._exit() call so tests can intercept it: a
    real exit inside a test process would kill the test runner.

    Args:
        code (int): Process exit code
    """
    os._exit(code)


def mod_entry(
    mod_name, config_name, child_conn, project_root='', mod_root='', path_main=''
):
    """
    Run mod scheduler infinitely

    Args:
        mod_name (str): Name of the mod to run
        config_name (str): Name of the config the worker runs
        child_conn (Connection): Worker side of the pipe, made by the parent
        project_root (str): Project root the child reports to, default to ''
        mod_root (str): Mod root the child chdirs into, default to ''
        path_main (str): Entry file of the mod, relative to mod_root,
            default to ''
    """
    # Test mods are defined in tests/backend/worker/worker_mods.py to keep
    # test code out of runtime, import lazily on demand.
    # A test worker is silenced BEFORE the bridge starts: the bridge recv
    # thread logs the command handling, and the parent can send a command as
    # soon as the worker reported "running" (the end of init), so a mute after
    # init would race with the first log line and leave a log file behind.
    is_test_mod = mod_name.startswith('WorkerTest')
    if is_test_mod:
        from tests.backend.worker.worker_mods import (
            WORKER_TEST_MODS,
            mute_test_worker_logging,
        )

        # a test worker must not open a log file in the real log directory
        mute_test_worker_logging()

    BackendBridge().init(mod_name, config_name, child_conn)

    if is_test_mod:
        try:
            worker = WORKER_TEST_MODS[mod_name]
        except KeyError:
            raise KeyError(f'No such mod to run {mod_name}') from None
        worker()
        return

    # if project_root, mod_root, path_main all provided, consider as real mod
    if project_root and mod_root and path_main:
        try:
            # set mod root path
            os.chdir(mod_root)
            sys.path[0] = mod_root

            # set project root path
            env.set_project_root(project_root)

            # import Scheduler
            entry = to_python_import(path_main)
            module = importlib.import_module(entry)
            try:
                cls = module.Scheduler
            except AttributeError:
                raise AttributeError('Module entry file did not define class Scheduler')

            # run mod scheduler
            scheduler = cls(config_name)
            scheduler.run()

        except KeyboardInterrupt:
            pass

    else:
        raise KeyError(f'No such mod to run {mod_name}')


def _async_raise(tid):
    """
    Inject a KeyboardInterrupt into a thread, the exception of the "killing" command

    The exception is only delivered when the thread reaches python bytecode again,
    a thread blocked in a native call keeps running until that call returns.

    Args:
        tid (int): Thread id to interrupt, e.g. the thread that runs the scheduler

    Returns:
        bool: True if the exception was injected, False if the thread is gone or
            the injection was rolled back
    """
    if tid <= 0:
        logger.error(
            f'[BackendBridge] Failed to send KeyboardInterrupt, tid invalid: {tid}'
        )
        return False

    import ctypes

    thread_id = ctypes.c_long(tid)
    err = ctypes.py_object(KeyboardInterrupt)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, err)

    if res == 1:
        return True
    if res == 0:
        # the thread is not there any more, nothing was injected
        logger.error(
            f'[BackendBridge] Failed to send KeyboardInterrupt, tid invalid: {tid}'
        )
        return False
    # more than one thread state was modified, which a thread id should not do:
    # the exception is pending on a thread this call did not aim at, take it back
    logger.error(f'[BackendBridge] Failed to send KeyboardInterrupt to thread {tid}')
    ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
    return False


class BackendBridge(metaclass=Singleton):
    def __init__(self):
        self.inited = False
        self.mod_name = ''
        self.config_name = ''
        self.conn = None

        self.main_tid = 0
        self._recv_thread: 'Thread | None' = None
        self._send_thread: 'Thread | None' = None
        self.scheduler_stopping = Event()
        self.preview_requested = PreemptiveEvent()
        # For test control
        self.test_wait = Event()

        # send thread
        # running: the bridge is alive and its backend is still there.
        # Cleared by close() (before the pipe is closed) and by
        # _handle_backend_lost() on pipe EOF, both of which turn send() into a
        # no-op and make the pipe loops stop.
        self.running = True
        # 初始为空，稍后存放 (bytes, threading.Lock)
        self._task_slot: 'tuple[bytes, Lock] | None' = None
        # 1. 互斥锁：保护 send 入口
        self._mutex = Lock()
        # 2. Worker 空闲信号：
        # Locked = Worker 忙; Unlocked = Worker 空闲
        self._worker_idle = Lock()
        # 3. 任务就绪信号：
        # Locked = 无任务; Unlocked = 有任务
        self._work_ready = Lock()
        self._work_ready.acquire()  # 初始锁定，让 Worker 待命

    def init(self, mod_name, config_name, child_conn):
        """
        Initialize BackendBridge in main thread
        """
        self.mod_name = mod_name
        self.config_name = config_name
        self.conn = child_conn
        self.main_tid = get_ident()

        self._send_thread = Thread(
            target=self._send_loop, daemon=True, name='BackendBridgeSender'
        )
        self._send_thread.start()
        self._recv_thread = Thread(
            target=self._recv_loop, daemon=True, name='BackendBridgeReceiver'
        )
        self._recv_thread.start()

        self.send_worker_state('running')
        self.inited = True

    @cached_property
    def _encoder(self):
        return Encoder()

    @cached_property
    def _decoder(self):
        return Decoder(CommandEvent)

    def send(self, event: ConfigEvent) -> Lock:
        """
        高性能事件发送

        1. 崩溃安全性 (Crash Safety) - "No-Queue Strategy":
           - 核心痛点：在高频日志场景下，使用 Queue 会导致内存中堆积大量未发送数据。一旦主进程崩溃（Crash），队列中所有数据瞬间丢失。
           - 解决方案：放弃队列，采用“单槽位（Single Slot）”设计。内存中永远最多只有 1 条正在处理的消息。
           - 收益：最大程度减少进程崩溃时的数据丢失窗口，仅限于当前正在 socket/pipe 中传输的那一条。

        2. 流量控制 (Back-Pressure):
           - 机制：当 Worker 线程正在发送上一条消息时，新的 send() 调用会在 _worker_idle 锁上发生物理阻塞。
           - 收益：自动平衡生产速度与消费（IO）速度。防止因日志产生过快导致内存暴涨（OOM）。
           - 行为：并发调用 send() 时，线程会排队等待槽位释放，严格保证串行化入管。

        3. 极致性能 (High Performance):
           - Zero-Copy: 数据仅通过引用传递，不进行 bytes 对象的内存复制（避免 append/pop 开销）。
           - Raw Bytes IO: 使用 pipe.send_bytes() 而非 pipe.send()，避开 pickle 序列化开销，直接传输二进制流。
           - Lightweight Locking: 仅使用 threading.Lock（底层 futex/semaphore），避免 Condition/Event 的额外开销。
           - Fast Path: 减少属性查找，Worker 内部使用局部变量缓存方法引用。

        4. 线程安全 (Thread Safety):
           - Lock Handoff: 使用锁传递机制（主线程 acquire，子线程 release）实现精确的同步接力。
           - Snapshotting: 将 (data, lock) 打包为元组，Worker 取出后即形成“本地快照”。
             即使实例属性在下一毫秒被新任务覆盖，Worker 手中的锁依然能正确通知对应的旧任务调用者。
        """
        conn = self.conn
        if not conn or not self.running:
            # allow worker running without backend, and drop events once the
            # backend is gone: blocking the caller on a send worker that never
            # runs again is worse than losing the event
            return Lock()

        data = self._encoder.encode(event)

        # 创建属于本次任务的专属锁
        # 调用者可以通过这个 lock.acquire() 等待消息真正发送完毕
        task_lock = Lock()
        # 预先锁住，用户只有在 Worker 释放后才能 acquire 成功
        task_lock.acquire()

        # 1. 竞争入口，防止多个线程同时修改共享数据
        self._mutex.acquire()
        try:
            # 2. 等待 Worker 空闲 (Back-pressure 核心)
            # 如果 Worker 正在发上一条，这里会阻塞，直到 Worker 释放锁
            self._worker_idle.acquire()

            # 3. 数据交接 (Zero Copy，只是引用赋值)
            # 将数据和锁打包在一起,这是一个原子赋值操作，不可分割。
            self._task_slot = (data, task_lock)

            # 4. 唤醒 Worker
            # 释放触发锁，允许 Worker 通过阻塞点
            self._work_ready.release()

            return task_lock

        finally:
            # 5. 释放入口锁
            # 注意：此时 _worker_idle 依然被持有（被当前线程获取，将在 Worker 线程释放）
            # 下一个调用者进来后，会在步骤 2 被阻塞，直到 Worker 完成本次任务。
            self._mutex.release()

    def _handle_backend_lost(self):
        """
        Stop the worker when the backend pipe reaches EOF

        Called by the recv loop: the backend crashed, was force killed or was
        shut down, nobody will ever consume worker events again, and a worker
        left behind keeps driving the device with nobody watching it.

        Two steps, the first one that works wins:

        1. inject a KeyboardInterrupt into the scheduler thread, the same thing
           the "killing" command does: a scheduler running python code unwinds
           and the process exits by itself. The injection is only delivered when
           that thread reaches a python bytecode boundary, so it cannot stop a
           scheduler blocked in a native call.
        2. if the scheduler thread is still running after
           BACKEND_LOST_KILL_WAIT_TIMEOUT, terminate the process directly.
           Skipping the scheduler cleanup is deliberate: it only holds task
           state, device connections and log buffers, which the interpreter and
           the OS reclaim when the process exits.
        """
        if not self.running:
            # close() closed the pipe (it clears `running` before touching the
            # pipe): that EOF is ours, the worker is shutting itself down and
            # must not be stopped here
            return

        self.running = False
        # logged before the stop, the log file is flushed per line
        logger.warning(
            f'[BackendBridge] Backend disconnected, stopping worker: "{self.config_name}"'
        )
        _async_raise(self.main_tid)

        # step 2: the injected exception is useless when the scheduler thread
        # never gets back to python code (it stays pending until the blocking
        # call returns)
        deadline = time.monotonic() + BACKEND_LOST_KILL_WAIT_TIMEOUT
        while time.monotonic() < deadline:
            if not main_thread().is_alive():
                # the injection worked, the process is exiting by itself
                return
            time.sleep(0.05)

        logger.warning(
            f'[BackendBridge] Scheduler did not stop in {BACKEND_LOST_KILL_WAIT_TIMEOUT}s, '
            f'terminating: "{self.config_name}"'
        )
        _exit_process(BACKEND_LOST_EXIT_CODE)

    def _release_pending_task(self):
        """
        Release the task lock of a task slot that will never be sent

        The send loop can stop while a task slot is still pending (the sender
        was woken by a task published in the race window of a shutdown), its
        caller is blocked on that lock and would never be woken up otherwise.
        """
        try:
            _, task_lock = self._task_slot
        except TypeError, ValueError:
            # no task pending, nothing to release
            return
        try:
            task_lock.release()
        except RuntimeError:
            # already released by the send loop
            pass

    def _send_loop(self):
        """
        后台 Worker 线程逻辑
        """
        # 本地缓存方法查找，微小的性能优化
        wait_for_work = self._work_ready.acquire
        signal_idle = self._worker_idle.release
        conn = self.conn

        while True:
            # 1. 等待任务 (阻塞)
            # 只有当 send() 调用 release() 时，这里才会通过
            wait_for_work()

            if not self.running:
                # stopping: a task may have been published right before, its
                # caller is waiting on the task lock and must be released
                self._release_pending_task()
                break

            try:
                data, task_lock = self._task_slot
            except TypeError, ValueError:
                # 防御性编程，处理可能的 None 或格式错误（虽然逻辑上不应发生）
                try:
                    signal_idle()
                except RuntimeError:
                    pass
                continue

            try:
                # 2. 发送数据
                # Equivalent to conn.send_bytes() but bypass all memorybuffer pre-checks
                conn._check_closed()
                conn._check_writable()
                conn._send_bytes(data)
            except AttributeError:
                # this shouldn't happen
                logger.error(
                    f'[BackendBridge] Failed to send command: pipe connection not initialized'
                )
                return False
            except EOFError, OSError:
                # pipe broken, the backend is gone: drop this event, the recv
                # loop owns the backend-lost handling (this loop must never
                # clear `running`, a cleared flag here would make a lost backend
                # look like close() to the recv loop). Keep looping: a caller
                # that is already waiting on a task lock is released by the
                # finally below, and the next wake-up stops this loop, because
                # the recv loop clears `running`
                # don't try to log back into the pipe to avoid deadlock
                # from alasio.logger import logger
                # logger.error(f'[BackendBridge] Failed to send command: pipe broken')
                pass
            except Exception as e:
                logger.error(f'[BackendBridge] Failed to send command: {e}')
            finally:
                # 3. 通知用户（如果用户在关心结果）
                # release 会让等待这个锁的用户线程继续执行
                try:
                    task_lock.release()
                except RuntimeError:
                    pass
                # 4. 标记 Worker 空闲
                # 释放锁，允许下一个 send() 调用通过步骤 2
                try:
                    signal_idle()
                except RuntimeError:
                    pass

    def _handle_backend_command(self, data: bytes):
        event = self._decoder.decode(data)
        command = event.c
        if command == 'preview':
            self.preview_requested.set()
            return
        if command == 'scheduler-stopping':
            logger.info(f'[BackendBridge] received command {command}')
            self.scheduler_stopping.set()
            return
        if command == 'scheduler-continue':
            logger.info(f'[BackendBridge] received command {command}')
            self.scheduler_stopping.clear()
            return
        if command in ['killing', 'force-killing']:
            logger.info(f'[BackendBridge] received command {command}')
            _async_raise(self.main_tid)
            return
        if command == 'test-continue':
            # Signal test_wait to continue immediately
            self.test_wait.set()
            self.test_wait.clear()
            return
        # ignore unknown events
        return

    def _recv_loop(self):
        conn = self.conn
        if not conn:
            # this shouldn't happen
            logger.error(
                f'[BackendBridge] Failed to recv command: pipe connection not initialized'
            )
            return False

        while self.running:
            try:
                data = conn.recv_bytes()
            except EOFError, OSError:
                # the backend is gone for good: stop the worker instead of
                # leaving it running as an orphan
                # don't try to log back into the pipe to avoid deadlock
                # from alasio.logger import logger
                # logger.error(f'[BackendBridge] Failed to recv command: pipe broken')
                self._handle_backend_lost()
                return False
            except Exception as e:
                logger.error(f'[BackendBridge] Failed to recv command: {e}')
                return False
            try:
                self._handle_backend_command(data)
            except Exception as e:
                logger.warning(f'[BackendBridge] Failed to handle command: {e}')
                continue

    def close(self):
        """
        Gracefully close the BackendBridge

        This method will:
        1. Set the closing flag to stop background threads
        2. Close the pipe connection
        3. Wait for threads to finish (with timeout)
        """
        if not self.inited:
            return

        # Set closing flag to stop threads from logging errors. It must be
        # cleared before the pipe is closed: the pipe loops use `running` to
        # tell an EOF caused by this close from an EOF caused by a dead backend.
        self.running = False

        # Close and NULLIFY connection to unblock recv_bytes() call
        conn = self.conn
        self.conn = None
        if conn is not None:
            try:
                conn.close()
            except:
                pass

        # Wake up send thread if it's waiting
        try:
            self._work_ready.release()
        except RuntimeError:
            pass

        # Wait for threads to finish with timeout
        if self._send_thread and self._send_thread.is_alive():
            self._send_thread.join(timeout=0.5)

        if self._recv_thread and self._recv_thread.is_alive():
            self._recv_thread.join(timeout=0.5)

        self.inited = False

    def send_log(self, value):
        return self.send(ConfigEvent(t='Log', v=value))

    def send_worker_state(
        self, value: Literal['running', 'scheduler-waiting', 'error']
    ):
        if value not in ['running', 'scheduler-waiting', 'error']:
            logger.error(f'[BackendBridge] Invalid worker state "{value}", ignored')
            return
        return self.send(ConfigEvent(t='WorkerState', v=value))
