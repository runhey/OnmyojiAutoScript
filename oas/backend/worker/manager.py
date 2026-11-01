"""
The WorkerManager: worker processes of the backend, their lifecycle and the
restart half of the maintenance flows.

Ported from alasio/backend/worker/manager.py (1433 lines, LF). The file is
kept upstream-identical: no member is trimmed, so the restart / update /
resume orchestration (restart_begin / restart_wait / restart_cancel /
mark_resume / drop_resume / worker_resume / worker_wait_started /
set_park_state / restart_abort / parked_configs / resume_intent / RestartRun)
stays in the file for the day that flow is ported. The two deviations, both
recorded in oas/backend/README.md:

- the import rewrites ``alasio.`` -> ``oas.`` (5 lines), nothing else;
- ``RESTART_MANAGER`` resolves to the minimal stand-in
  ``oas/backend/app/restart/restart_manager.py`` instead of upstream's
  ``restart_manager`` (the OAS backend has no ``app/restart`` package yet).
  The stand-in answers the only two members this module reads -- ``frozen``
  (upstream manager.py:499, :1219) and ``flow_running`` (:505) -- with False,
  so no maintenance flow owns the backend and every start proceeds directly.

trio: the module never imports it, but four docstrings of the restart members
still name it (upstream runs the restart wait / queue through
``trio.to_thread.run_sync`` in the caller: the RestartRun docstring,
restart_wait, parked_configs and resume_intent); they are kept verbatim, to be
reworded for anyio when the real restart package lands.
"""

import multiprocessing
import socket
import threading
import time
from multiprocessing.connection import Connection
from typing import List, Literal, Optional

import msgspec
from msgspec.msgpack import encode

from oas.backend.app.restart.restart_manager import RESTART_MANAGER
from oas.backend.worker.bridge import mod_entry
from oas.backend.worker.event import DECODER_CACHE, CommandEvent, ConfigEvent
from oas.ext.singleton import Singleton
from oas.logger import logger

# idle: not running
# starting: requesting to start a worker, starting worker process
# running: worker process running
# scheduler-stopping: requesting to stop scheduler loop, worker will stop after current task
# scheduler-waiting: worker waiting for next task, no task running currently
# killing: requesting to kill a worker, worker will stop and do GC asap.
#   worker_kill() waits KILL_WAIT_TIMEOUT for the worker to stop by itself,
#   then escalates to force-killing
# force-killing: requesting to kill worker process immediately
# disconnected: backend just lost connection worker,
#   worker process will be clean up and worker status will turn into idle or error very soon
# error: worker stopped with error
#   Note that scheduler will loop forever, so there is no "stopped" state
#   If user request "scheduler_stopping" or "killing", state will later be "idle"
# restarting: worker stopped because of a graceful backend restart, the backend
#   will auto-resume it after the restart. The entry stays in the state dict
#   (occupies the config, manual start rejected) and restart_wait() collects it
#   into the resume list. Manual start is rejected.
# updating: the same as restarting, but the flow stopping the workers belongs
#   to an update / daily / startup flow (the flow set the parked state through
#   set_park_state() before it stopped them): the frontend shows "updating"
#   instead of "restarting", every other behavior (park / collect / resume /
#   refusal) is identical.
# resuming: queued for auto-resume after the backend restart (no process yet).
#   The new backend builds the queue with mark_resume() and starts the entries
#   one by one through worker_resume(), each one after the previous worker
#   reported itself (worker_wait_started).
WORKER_STATE = Literal[
    'idle',
    'starting',
    'running',
    'disconnected',
    'error',
    'scheduler-stopping',
    'scheduler-waiting',
    'killing',
    'force-killing',
    'restarting',
    'updating',
    'resuming',
]
# Allow worker set its state to one of the allows
WORKER_STATE_ALLOWS = ['running', 'scheduler-waiting']
# Worker is considered running if state in the followings
WORKER_RUNNING_STATE = ['running', 'scheduler-stopping', 'scheduler-waiting']
# Worker is considered stopped if state in the followings
WORKER_STOPPED_STATE = ['idle', 'error', 'restarting', 'updating', 'resuming']
# The park states (a subset of WORKER_STATE): the state a worker stopped by
# a maintenance flow in progress is parked in -- 'updating' for an update /
# daily / startup flow, 'restarting' for a restart flow. The flow in flight
# sets it through set_park_state() before it stops the workers.
WORKER_PARK_STATE = Literal['restarting', 'updating']
# The park states as a runtime list, for the membership checks (a typing
# Literal itself cannot be used with `in`)
WORKER_PARKED_STATE = ['restarting', 'updating']

# Seconds to wait for a worker to stop by itself in worker_kill(),
# before the kill is escalated to worker_force_kill()
KILL_WAIT_TIMEOUT = 1.0

# Poll interval of restart_wait() while it blocks for the workers to stop.
# The wait itself is a 10-minute scale wait; the poll only has to keep the
# abort event (restart_cancel) and worker stops reasonably responsive.
RESTART_WAIT_POLL = 0.1


class WorkerState(msgspec.Struct):
    mod: str
    config: str
    state: WORKER_STATE
    update: float = 0.0
    # True while the worker is stopped for a maintenance flow of the backend:
    # the disconnect handler then turns it into "restarting" (instead of
    # idle/error) and restart_wait() collects the config into the resume list.
    # Cleared when the user cancels the pending resume (stop / kill with the
    # default restart_resume=False) or when the worker starts again.
    pending_restart: bool = False

    process: Optional[multiprocessing.Process] = None
    conn: Optional[Connection] = None
    running_event: threading.Event = msgspec.field(default_factory=threading.Event)
    stopped_event: threading.Event = msgspec.field(default_factory=threading.Event)
    # Set by every state this entry goes through (see set_state), whatever the
    # side that set it: worker_wait_started() waits on it for the entry to leave
    # its spawn window, so an entry finalized without a report of the worker (a
    # flow stopping it, a disconnect) is seen at once rather than at the timeout
    changed_event: threading.Event = msgspec.field(default_factory=threading.Event)
    recv_thread: Optional[threading.Thread] = None

    def set_state(self, state: WORKER_STATE):
        self.state = state
        self.update = time.time()
        self.changed_event.set()
        if state in WORKER_RUNNING_STATE:
            self.running_event.set()
            self.stopped_event.clear()
        elif state in WORKER_STOPPED_STATE:
            self.running_event.clear()
            self.stopped_event.set()
        else:
            self.running_event.clear()
            self.stopped_event.clear()

    def send_command(self, command: CommandEvent):
        data = encode(command)
        try:
            conn = self.conn
            # Equivalent to  conn.send_bytes() but bypass all by
            conn._check_closed()
            conn._check_writable()
            conn._send_bytes(data)
            return True
        except AttributeError:
            # no pipe attached: the worker was cleaned up in between (the state
            # checks passed before the disconnect handler cleared state.conn).
            # A worker in its spawn window always has its pipe registered
            # (see _mark_starting_locked), so a stop request is never dropped
            logger.warning(
                f'[WorkerManager] Failed to send command config="{self.config}", command={command}: '
                f'pipe connection not initialized'
            )
            return False
        except Exception as e:
            logger.warning(
                f'[WorkerManager] Failed to send command config="{self.config}", command={command}: {e}'
            )
            return False

    def send_test_continue(self):
        event = CommandEvent(c='test-continue')
        return self.send_command(event)

    def wait_running(self, timeout: 'float | None' = None):
        return self.running_event.wait(timeout)

    def wait_stopped(self, timeout: 'float | None' = None):
        return self.stopped_event.wait(timeout)

    def conn_close(self):
        """
        Close pipe if pipe opened
        """
        conn = self.conn
        if not conn:
            return
        if isinstance(conn, Connection):
            # On POSIX the pipe of a duplex Pipe() is a socketpair and the recv thread
            # reads it with a blocking os.read(): closing the fd does not wake a read
            # blocked in another thread, only data, EOF or shutdown() do. Without the
            # shutdown the thread survives until the worker process closes its end
            # (a worker that is gone already does not, e.g. a failed spawn), so the
            # thread would leak past close() / force-kill.
            try:
                sock = socket.socket(fileno=conn.fileno())
            except OSError, ValueError:
                pass
            else:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    # not a socket (a pipe built with os.pipe), close() still applies
                    pass
                finally:
                    sock.detach()
        try:
            conn.close()
        except Exception:
            pass

    def process_join(self, timeout):
        process = self.process
        if process and process.is_alive():
            process.join(timeout)

    def process_terminate(self):
        """
        Close process if process started
        """
        process = self.process
        if not process:
            return
        if process.is_alive():
            logger.info(f'[WorkerManager] Terminating worker process: "{self.config}"')
            try:
                process.terminate()
            except Exception as e:
                logger.error(
                    f'[WorkerManager] Error while terminating "{self.config}": {e}'
                )

    def process_kill(self, timeout=1):
        """
        Close process if process started
        """
        process = self.process
        if not process:
            return
        if process.is_alive():
            logger.info(
                f'[WorkerManager] Force killing worker process: "{self.config}"'
            )
            try:
                process.kill()
                process.join(timeout=timeout)
                # no luck
                if process.is_alive():
                    logger.info(
                        f'[WorkerManager] Worker still alive after force-kill: "{self.config}"'
                    )
            except Exception as e:
                logger.error(
                    f'[WorkerManager] Error while force-killing "{self.config}": {e}'
                )

    def process_graceful_kill(self, terminate_timeout=1, kill_timeout=1):
        """
        Close process if process started
        """
        process = self.process
        if not process:
            return
        if process.is_alive():
            logger.info(f'[WorkerManager] Graceful killing process: "{self.config}"')
            try:
                # try graceful terminate() first
                process.terminate()
                process.join(timeout=terminate_timeout)
                if process.is_alive():
                    # then try force-kill
                    logger.info(
                        f'[WorkerManager] Worker did not terminate, force killing process: "{self.config}"'
                    )
                    process.kill()
                    process.join(timeout=kill_timeout)
                # no luck
                if process.is_alive():
                    logger.info(
                        f'[WorkerManager] Worker still alive after force-kill: "{self.config}"'
                    )
            except Exception as e:
                logger.error(
                    f'[WorkerManager] Error while force-killing "{self.config}": {e}'
                )


class RestartRun:
    """
    State of one graceful restart orchestration (restart_begin /
    restart_wait / restart_cancel)

    One instance exists while a graceful restart owns the manager (and stays
    on the success path until the process exits). Its frozen resume list is
    exactly the list the orchestration records in the resume file; a stop
    request on one of its configs after the wait is refused with an explicit
    error instead of cancelling something the file keeps (F4).

    Attributes:
        abort (threading.Event): Set by restart_cancel() to make a blocking
            restart_wait() return early with (False, []): a trio cancel cannot
            interrupt the waiting thread, the abort event is the cooperative
            wake-up
        resume_frozen (set[str]): The frozen resume list of this run
        frozen (bool): True when restart_wait() froze resume_frozen: the
            resume file is written from it, so a start accepted as a queued
            resume afterwards could never be resumed -- it is refused instead
            of being lost silently (see _queue_update_start_locked)
    """

    def __init__(self):
        self.abort = threading.Event()
        self.resume_frozen: 'set[str]' = set()
        self.frozen = False


class WorkerManager(metaclass=Singleton):
    def __init__(self):
        self._lock = threading.Lock()

        # dict of worker state
        # if config not in self.state, its status is default to "idle"
        self.state: 'dict[str, WorkerState]' = {}

        self._ctx = multiprocessing.get_context('spawn')

        # Graceful restart orchestration in flight (restart_begin /
        # restart_wait / restart_cancel): one RestartRun while a graceful
        # restart owns this manager, None otherwise. The gate is kept until
        # the process exits on the success path (restart_cancel releases it).
        self._restart: 'Optional[RestartRun]' = None

        # The state the workers stopped by the maintenance flow in flight are
        # parked in ('updating' for an update / daily / startup flow,
        # 'restarting' for a restart flow): the frontend shows what the flow is
        # doing, everything else about the parked entries is the same. The
        # flows set it through set_park_state() before they stop the workers.
        self.park_state: WORKER_PARK_STATE = 'restarting'

    @property
    def restarting(self) -> bool:
        """
        Whether a graceful restart owns this manager (the restart gate)

        A RestartRun exists from restart_begin() and is kept until
        restart_cancel() releases it (or the process exits on the success
        path). While it is on, every way in which a worker can be started is
        refused: worker_start() (a worker started now would die with the
        backend and never resume), worker_resume() and mark_resume() -- the
        resume queue of the new backend stops there, the graceful restart
        re-collects its marks instead.

        Read without the lock: it is a hint for the auto-resume task to end
        early when a restart takes the backend over, the authoritative refusal
        happens in the locked entry points above.

        Returns:
            bool: True while a graceful restart is in progress
        """
        return self._restart is not None

    def get_state_info(self):
        """
        Returns:
            dict[str, WORKER_STATE]: key: config name, value: worker state
        """
        out = {}
        with self._lock:
            for w in self.state.values():
                out[w.config] = w.state
        return out

    def _handle_disconnect(self, state: WorkerState):
        """
        Cleanup worker on pipe broken
        """
        with self._lock:
            state_before = state.state
            # A disconnect publishes state only for the entry currently registered
            # for the config: an entry that was closed (manager close) or already
            # finalized / replaced has its state decided there -- publishing here
            # would resurrect a stale one or clobber the new entry of the config.
            publish = self.state.get(state.config, None) is state
            if publish:
                self._set_state(state, 'disconnected')

        process = state.process
        if process:
            # after pipe broken, process should terminate every soon
            if process.is_alive():
                # On Windows, process needs a bit of time for handle cleanup
                # 0.5s is usually enough if child closed pipe manually
                process.join(timeout=0.5)
            # otherwise, kill it manually
            state.process_graceful_kill()

        # Close connection to unblock recv thread
        state.conn_close()

        # Join recv thread if it is not the current thread
        recv_thread = state.recv_thread
        if recv_thread and recv_thread is not threading.current_thread():
            if recv_thread.is_alive():
                recv_thread.join(timeout=1)

        exitcode = process.exitcode if process else None
        self.on_worker_info(
            state.config,
            f'[WorkerManager] Worker stopped: {state.config}, exitcode={exitcode}',
        )

        with self._lock:
            state.conn = None
            state.process = None
            state.recv_thread = None
            if not publish:
                return
            if state.pending_restart:
                # stopped for the graceful backend restart: park the worker in
                # "updating" / "restarting" (the entry stays in the dict, blocks
                # a manual start and is collected into the resume list by
                # restart_wait()); a crashed startup is still restarted, the
                # new backend simply retries the same way a manual start does
                self._set_state(state, self.park_state)
            elif exitcode == 0:
                self._set_state(state, 'idle')
            else:
                if state_before in ['killing', 'force-killing']:
                    # already killing, ignore exitcode because worker will exit with error
                    self._set_state(state, 'idle')
                else:
                    self._set_state(state, 'error')

    def on_config_event(self, event: ConfigEvent):
        """
        Callback when received config event from worker

        The base manager has no event consumer (the app layer overrides this to
        feed the topic layer), so the event is only logged for debugging. It
        must not be printed: the callback runs on the manager's recv thread, so
        a print lands outside pytest's capture window and dumps raw events into
        the test output.

        Args:
            event (ConfigEvent): Event received from the worker
        """
        logger.debug(f'[WorkerManager] Unhandled config event: {event}')

    def on_worker_info(self, config: str, msg: str):
        """
        Callback when logging worker info
        """
        logger.info(msg)
        event = logger.backend_event(msg, raw=1)
        event = ConfigEvent(t='Log', c=config, v=event)
        self.on_config_event(event)

    def _handle_config_event(self, data: bytes, worker: WorkerState):
        """
        Interval method to handle config event
        """
        event = DECODER_CACHE.CONFIG_EVENT.decode(data)

        # override config to avoid cross-mod or cross-config event pollution
        # we don't trust the "config" from worker, "config" can only be worker itself
        event.c = worker.config

        # handle "WorkerState" events
        if event.t == 'WorkerState':
            if event.v in WORKER_STATE_ALLOWS:
                with self._lock:
                    if worker.state in WORKER_STATE_ALLOWS:
                        # allow worker switching its state among allows
                        self._set_state(worker, event.v)
                        return
                    if worker.state == 'starting':
                        # allow worker switching to allows from "starting"
                        self._set_state(worker, event.v)
                        return
            return

        # broadcast
        self.on_config_event(event)

    def on_worker_state(self, config: str, state: WORKER_STATE):
        """
        Callback when worker state changed

        Like on_config_event: the base manager only logs (the app layer
        overrides this to broadcast the Worker topic), and it must not print
        from the recv thread.

        Args:
            config (str): Config name
            state (WORKER_STATE): New worker state
        """
        logger.debug(f'[WorkerManager] Worker state "{config}": {state}')

    def _set_state(self, worker: WorkerState, state: WORKER_STATE):
        """
        Internal method to set worker state, lock required
        """
        worker.set_state(state)
        if state == 'idle':
            # remove worker state
            self.state.pop(worker.config, None)
        # broadcast
        self.on_worker_state(worker.config, state)

    def _worker_recv_loop(self, state: WorkerState):
        """
        Thread entry to receive message from worker

        我们给每个Worker进程单独开一个线程循环接收消息，而不是像web服务一样使用 wait(list_pipe) 同时接收所有消息
        在真实运行场景下，log是稀疏产生的，而一旦有log很可能是短时间内产生大量log
        wait(list_pipe) 虽然对多个pipe有很好的接收性能，但是对单一pipe的高频接收就远不如直接 conn.recv_bytes() 了。

        多线程recv_bytes() 的问题是同时接收多个pipe的时候会有频繁GIL切换导致性能远不如 wait(list_pipe)
        但因为log是稀疏产生的，每个worker的高频时段通常不会集中，所以在我们的运行情景下
        使用 多线程recv_bytes() 的性能就是单线程 recv_bytes()
        """
        conn = state.conn
        config = state.config
        try:
            while True:
                # check if pipe closed
                if not state.conn:
                    break
                try:
                    data = conn.recv_bytes()
                except EOFError, OSError:
                    break

                try:
                    self._handle_config_event(data, state)
                except Exception as e:
                    logger.warning(
                        f'[WorkerManager] Failed to handle config event '
                        f'from "{config}": {e}'
                    )
        except Exception as e:
            logger.error(f'[WorkerManager] Recv loop error "{config}": {e}')

        # Handle disconnect
        self._handle_disconnect(state)

    def worker_start(
        self, mod: str, config: str, project_root='', mod_root='', path_main=''
    ) -> 'tuple[bool, str]':
        """
        Request to start a worker
        Note that this method does not check if mod and config are valid

        Returns:
            whether success, reason
        """
        with self._lock:
            if RESTART_MANAGER.frozen:
                # the resume intent of a maintenance flow is published and the
                # process is about to be replaced: the configs of the file are
                # the resume list, a start accepted now could never be resumed
                return False, (
                    f'Backend is restarting, start the config after the restart: '
                    f'"{config}"'
                )
            if RESTART_MANAGER.flow_running:
                # a maintenance flow owns the backend: the start is accepted as
                # a queued resume instead of being refused (the flow releases
                # the queue on its way out, see the resume queue section)
                return self._queue_update_start_locked(mod, config)
            if self.restarting:
                # any worker started now would be killed when the backend exits
                # and would never resume ("started but lost")
                return False, (
                    f'Backend is gracefully restarting, workers will resume '
                    f'after restart, cannot start now: "{config}"'
                )
            # get or init config state
            state = self.state.get(config, None)
            if not state:
                state = WorkerState(mod=mod, config=config, state='idle')
                self.state[config] = state
            # check if already started
            if state.state not in ['idle', 'error']:
                if state.state == 'resuming':
                    return (
                        False,
                        f'Worker is queued for auto-resume after restart: "{config}"',
                    )
                if state.state in WORKER_PARKED_STATE:
                    return False, (
                        f'Worker is stopped for the backend restart in progress '
                        f'and will auto-resume: "{config}"'
                    )
                return (
                    False,
                    f'Worker is already running: "{config}", state="{state.state}"',
                )
            # mark immediately
            state.mod = mod
            state.pending_restart = False
            child_conn = self._mark_starting_locked(state)

        self.on_worker_info(config, f'[WorkerManager] Starting worker: {config}')
        return self._worker_start_process(
            state, mod, config, child_conn, project_root, mod_root, path_main
        )

    def _mark_starting_locked(self, state: WorkerState) -> Connection:
        """
        Mark the worker as "starting" with its pipe already open (lock required)

        The pipe is opened before the state becomes visible, so a "starting"
        worker always has one: a command sent while the process spawns is written
        into the pipe and buffered by the OS until the worker reads its end.
        Setting the state first would leave the spawn window without a pipe -- a
        stop request landing in it would be dropped and the worker would keep
        running while the manager believes it is stopping (a graceful restart
        would then only end through the timeout escalation).

        Returns:
            Connection: The child end of the pipe, to be handed to the spawned
                process (the parent end is registered as state.conn)
        """
        parent_conn, child_conn = self._ctx.Pipe()
        state.conn = parent_conn
        self._set_state(state, 'starting')
        return child_conn

    def _worker_start_process(
        self,
        state: WorkerState,
        mod: str,
        config: str,
        child_conn,
        project_root='',
        mod_root='',
        path_main='',
    ) -> 'tuple[bool, str]':
        """
        Spawn the worker process and its recv thread (lock released)

        The caller must have marked the worker as "starting" under the lock and
        opened its pipe (_mark_starting_locked): worker_start() and
        worker_resume() share this tail.

        Returns:
            whether success, reason
        """
        if project_root and mod_root and path_main:
            # if project_root, mod_root, path_main all provided, consider as real mod
            args = (mod, config, child_conn, project_root, mod_root, path_main)
        else:
            # otherwise just testing
            args = (mod, config, child_conn)
        process = self._ctx.Process(
            target=mod_entry, args=args, name=f'Worker-{mod}-{config}', daemon=True
        )
        try:
            process.start()
        except Exception as e:
            # Spawning failed in the parent (the interpreter / OS could not create
            # the process, or the startup data could not be sent): no process
            # exists and none will ever report for this entry, so it must not stay
            # "starting" -- the config could not be started again and no
            # disconnect would ever finalize it. A child that dies after start()
            # returned (import error, broken mod, scheduler crash) is the
            # disconnect path's business: its pipe reaches EOF and the entry is
            # finalized as usual (error / restarting).
            state.conn_close()
            with self._lock:
                state.conn = None
                # a marked worker is parked like a crashed startup (the new
                # backend retries it), an unmarked one returns to error
                self._set_state(
                    state, self.park_state if state.pending_restart else 'error'
                )
            logger.exception(e)
            raise
        # close child_conn of the parent side immediately
        child_conn.close()

        with self._lock:
            state.process = process
            # status will become "running" when worker process initialize BackendBridge

            # start recv thread
            thread = threading.Thread(
                target=self._worker_recv_loop,
                args=(state,),
                name=f'WorkerRecv-{config}',
                daemon=True,
            )
            thread.start()
            state.recv_thread = thread

        return True, 'Success'

    def worker_wait_running(self, config: str, timeout: 'float | None' = None) -> bool:
        """
        Wait until worker running

        Returns:
            If waited
        """
        # dict access is thread safe, so no lock needed
        try:
            state = self.state[config]
        except KeyError:
            raise KeyError(f'No such worker: {config}') from None
        return state.wait_running(timeout)

    def worker_wait_stopped(self, config: str, timeout: 'float | None' = None) -> bool:
        """
        Wait until worker stopped

        Returns:
            If waited
        """
        try:
            state = self.state[config]
        except KeyError:
            # No such worker means not yet running or stopped
            return True
        return state.wait_stopped(timeout)

    def worker_scheduler_stop(
        self, config: str, restart_resume=False
    ) -> 'tuple[bool, str]':
        """
        Send "scheduler-stopping" to worker

        Args:
            config (str): Config name
            restart_resume (bool): Only meaningful for a worker already stopped
                for the restart ("restarting", no process): True keeps the
                pending resume, False (default) cancels it

        Returns:
            whether success, reason
        """
        with self._lock:
            # get config state
            state = self.state.get(config, None)
            if not state:
                return False, f'No such worker to stop: {config}'
            # process-less restart states: a stop cancels the auto-resume
            result = self._cancel_or_keep_resume(state, restart_resume)
            if result is not None:
                return result
            # check if worker is running
            if state.state in ['idle', 'error', 'disconnected']:
                return False, f'Worker not running: "{config}", state="{state.state}"'
            if state.state in ['scheduler-stopping']:
                return (
                    False,
                    f'Worker is already stopping: "{config}", state="{state.state}"',
                )
            if state.state in ['killing', 'force-killing']:
                return (
                    False,
                    f'Worker is already killing: "{config}", state="{state.state}"',
                )
            # mark immediately
            self._set_state(state, 'scheduler-stopping')

        self.on_worker_info(
            config, f'[WorkerManager] Requesting scheduler stop: {config}'
        )
        # send command without lock
        command = CommandEvent(c='scheduler-stopping')
        state.send_command(command)

        return True, 'Success'

    def worker_scheduler_continue(self, config: str) -> 'tuple[bool, str]':
        """
        Send "scheduler-continue" to worker, to cancel previous "scheduler-stopping"

        Returns:
            whether success, reason
        """
        with self._lock:
            # get config state
            state = self.state.get(config, None)
            if not state:
                return False, f'No such worker to stop: {config}'
            if state.pending_restart:
                # the worker is already part of the graceful restart, the stop
                # cannot be revoked
                return (
                    False,
                    f'Worker is stopping for backend restart, cannot continue: "{config}"',
                )
            # check if worker is running
            if state.state in ['idle', 'error', 'disconnected']:
                return False, f'Worker not running: "{config}", state="{state.state}"'
            if state.state in ['killing', 'force-killing']:
                return (
                    False,
                    f'Worker is already killing: "{config}", state="{state.state}"',
                )
            if state.state not in [
                'scheduler-stopping',
            ]:
                return (
                    False,
                    f'Worker is not in scheduler-stopping: "{config}", state="{state.state}"',
                )
            # mark immediately
            self._set_state(state, 'running')

        self.on_worker_info(
            config, f'[WorkerManager] Requesting scheduler continue: {config}'
        )
        # send command without lock
        command = CommandEvent(c='scheduler-continue')
        state.send_command(command)

        return True, 'Success'

    def worker_kill(self, config: str, restart_resume=False) -> 'tuple[bool, str]':
        """
        Send "killing" to worker, wait for the worker to stop by itself

        The call blocks until the worker stops. If the worker does not stop
        within KILL_WAIT_TIMEOUT seconds, escalate to worker_force_kill().
        A worker that is still spawning has no process to stop yet: its kill
        request is buffered by its pipe and it stops as soon as it boots (the
        call returns without waiting for that boot, see worker_force_kill()).

        Args:
            config (str): Config name
            restart_resume (bool): Only meaningful while a graceful restart is
                waiting: True stops the worker but keeps the pending resume
                (it still resumes after the backend restart), False (default)
                stops the worker for good (the config leaves the resume list)

        Returns:
            whether success, reason
        """
        with self._lock:
            # get config state
            state = self.state.get(config, None)
            if not state:
                return False, f'No such worker to kill: {config}'
            # process-less restart states: a stop cancels (or keeps) the auto-resume
            result = self._cancel_or_keep_resume(state, restart_resume)
            if result is not None:
                return result
            # check if worker is running
            if state.state in ['idle', 'error', 'disconnected']:
                return False, f'Worker not running: "{config}", state="{state.state}"'
            if state.state in ['killing', 'force-killing']:
                return (
                    False,
                    f'Worker is already killing: "{config}", state="{state.state}"',
                )
            if not restart_resume:
                # default stop cancels the pending resume: the worker stops and
                # does not come back after the backend restart
                state.pending_restart = False
            # mark immediately
            self._set_state(state, 'killing')

        self.on_worker_info(config, f'[WorkerManager] Requesting worker kill: {config}')
        # send command without lock
        command = CommandEvent(c='killing')
        state.send_command(command)

        # Wait for worker to stop by itself
        if state.wait_stopped(timeout=KILL_WAIT_TIMEOUT):
            return True, 'Success'

        # Worker did not stop by itself, escalate to force kill
        self.on_worker_info(
            config,
            f'[WorkerManager] Worker did not stop by itself within {KILL_WAIT_TIMEOUT}s, force killing: {config}',
        )
        success, msg = self.worker_force_kill(config, restart_resume=restart_resume)
        if not success:
            # Worker may have just stopped by itself, or is being stopped by another request,
            # the worker is no longer running, so the kill is considered successful
            self.on_worker_info(
                config,
                f'[WorkerManager] Worker already stopped, force kill skipped: {msg}',
            )

        return True, 'Success'

    def worker_force_kill(
        self, config: str, restart_resume=False
    ) -> 'tuple[bool, str]':
        """
        Request to force kill a worker

        Args:
            config (str): Config name
            restart_resume (bool): Only meaningful while a graceful restart is
                waiting: True keeps the pending resume (the worker is killed
                now and still resumes after the backend restart), False
                (default) stops the worker for good

        Returns:
            whether success, reason
        """
        with self._lock:
            # get or init config state
            state = self.state.get(config, None)
            if not state:
                return False, f'No such worker to force-kill: {config}'
            # process-less restart states: a stop cancels (or keeps) the auto-resume
            result = self._cancel_or_keep_resume(state, restart_resume)
            if result is not None:
                return result
            # check if already killed
            if state.state in ['idle', 'error', 'disconnected']:
                return False, f'Worker not running: "{config}", state="{state.state}"'
            if state.state in ['force-killing']:
                return (
                    False,
                    f'Worker is already force-killing: "{config}", state="{state.state}"',
                )
            if not restart_resume:
                # default stop cancels the pending resume (see worker_kill)
                state.pending_restart = False
            # mark immediately
            self._set_state(state, 'force-killing')
            # read with the state transition: the process is registered by
            # _worker_start_process() once process.start() returned
            spawned = state.process is not None

        if not spawned:
            # The worker is still spawning: there is no process to terminate yet.
            # The kill travels through the pipe -- a "starting" worker always has
            # one (see _mark_starting_locked) -- so the worker stops itself the
            # moment it boots, and its own disconnect finalizes the entry.
            # Finalizing it here would leave the process created afterwards
            # untracked while the manager already reported it as stopped.
            state.send_command(CommandEvent(c='force-killing'))
            return True, 'Success'

        # cleanup
        state.process_graceful_kill()
        state.conn_close()
        if state.recv_thread and state.recv_thread.is_alive():
            state.recv_thread.join(timeout=1)

        with self._lock:
            state.process = None
            state.conn = None
            state.recv_thread = None
            if state.pending_restart:
                # stopped for the maintenance flow: park in "updating" /
                # "restarting" so restart_wait() collects the config into the
                # resume list
                self._set_state(state, self.park_state)
            else:
                self._set_state(state, 'idle')

        return True, 'Success'

    def _cancel_or_keep_resume(
        self, state: WorkerState, restart_resume: bool
    ) -> 'Optional[tuple[bool, str]]':
        """
        Routing of the stop functions for the process-less restart states (lock required)

        A stop request on these states means "cancel the auto-resume": the
        entry returns to idle and leaves the resume list / queue. The single
        exception is "restarting" with restart_resume=True: the worker is
        already stopped, keep waiting (no-op success). "resuming" is always
        cancelled (no process exists, any stop means cancel).

        A frozen resume list (RestartRun.resume_frozen, set when restart_wait()
        ended) refuses the cancel of a "restarting" entry it contains with an
        explicit error: the resume file is written from exactly that list, so
        dropping the entry here would cancel nothing but the manager state and
        the config would still resume (F4). An entry outside the list holds no
        recorded resume intent, so its cancel is honoured like any other stop
        (nothing resumes the config, the two semantics do not conflict). The
        refusal is a plain failed call result, which the rpc layer turns into an
        RpcValueError for the frontend.

        Args:
            state (WorkerState): Worker state, looked up under the lock
            restart_resume (bool): True keeps the pending resume of
                "restarting"; ignored for "resuming"

        Returns:
            Optional[tuple[bool, str]]: The call result when the state is
                "restarting" / "updating" / "resuming" (such a request is
                always answered here: keep-resume no-op, the refusal of a
                recorded config, or the cancel), None for any other state (the
                caller continues with its normal routing, which needs a live
                process)
        """
        if state.state in WORKER_PARKED_STATE:
            if restart_resume:
                # the worker is already stopped for the restart, keep waiting
                return True, 'Success'
            run = self._restart
            if run is not None and state.config in run.resume_frozen:
                return False, (
                    f'Restart is beyond the point of no return, the config will be resumed '
                    f'after the backend restart: "{state.config}"'
                )
            # not recorded for the resume: no conflict, the stop cancels the
            # auto-resume like any other (falls through, never returns None --
            # the caller's routing would send a command to a process that does
            # not exist and leave a stuck entry behind)
        elif state.state != 'resuming':
            # not a process-less restart state: the caller owns the routing
            return None
        # cancel the auto-resume: clear the mark, drop the entry, report success
        state.pending_restart = False
        self._set_state(state, 'idle')
        self.on_worker_info(
            state.config, f'[WorkerManager] Auto resume cancelled: {state.config}'
        )
        return True, 'Success'

    # ---------------- graceful restart orchestration ----------------

    def restart_begin(self) -> 'List[str]':
        """
        Begin a graceful backend restart

        Runs under one lock: sets the restarting gate, snapshots the running
        workers ({starting, running, scheduler-waiting}) and marks them
        "pending_restart", and converts the entries queued by a previous
        auto-resume ("resuming") into "restarting" so this restart collects
        them too: the resume intent of a queue that is still being built or
        drained becomes this restart's resume list. The stop requests are sent
        outside the lock. The call returns immediately, the wait belongs to
        restart_wait().

        Returns:
            List[str]: Sorted configs the wait will cover -- every worker that
                is not stopped yet, including the ones already stopping from
                an earlier request. Meant for the caller's log ("waiting for
                these configs"); the final resume list is the return value of
                restart_wait()

        Raises:
            RuntimeError: When a graceful restart is already in progress
        """
        with self._lock:
            if self._restart is not None:
                raise RuntimeError('Restart already in progress')
            # gate and snapshot under the same lock as worker_start's check:
            # no worker can slip between the gate and the snapshot
            self._restart = RestartRun()
            running = [
                state
                for state in self.state.values()
                if state.state in ['starting', 'running', 'scheduler-waiting']
            ]
            for state in running:
                state.pending_restart = True
            # a resume queue of a previous restart that has not been drained
            # yet (the backend is restarted again right after): the entries
            # have no process and are already "stopped for restart", turn
            # them into "restarting" (with the mark) so restart_wait() collects
            # them into this restart's resume list. A queue that is still being
            # built (mark_resume) or waiting for the config scan has the same
            # entries by then -- that is the handover -- and a queue whose task
            # sees this gate refuses to build more (mark_resume / worker_resume)
            # and ends early
            for state in list(self.state.values()):
                if state.state == 'resuming':
                    state.pending_restart = True
                    self._set_state(state, self.park_state)
            waiting = self._restart_pending_configs_locked()

        # send the graceful stop requests outside the lock (worker_scheduler_stop
        # takes the lock itself); a "starting" worker gets the command queued
        # in the pipe and exits from its earliest checkpoint
        for state in running:
            self.worker_scheduler_stop(state.config)

        return waiting

    def restart_wait(self, timeout=None) -> 'tuple[bool, List[str]]':
        """
        Block until every worker stopped for the graceful restart

        Must run in its own thread (the async orchestrator calls it through
        trio.to_thread.run_sync): the wait can last up to the timeout. It runs
        in two phases:

        1. the graceful wait: every worker gets `timeout` seconds to stop by
           itself (None waits forever);
        2. when the timeout ended it, the escalation: every worker still
           running is killed through worker_kill(restart_resume=True), which
           itself escalates to a force kill (a kill of a worker still spawning
           is buffered by its pipe and lands when the worker boots), and the
           wait continues without a deadline until all of them stopped.

        Both phases poll (RESTART_WAIT_POLL) and restart_cancel() (abort) makes
        the wait return from either of them: it then reports the cancellation
        (False) and the caller must not continue with the restart -- the cancel
        path owns the state cleanup and no resume file may be written.

        On success the returned list is frozen by this call (see
        _freeze_restart_resume_list): the orchestration writes exactly it into
        the resume file, so a stop request on one of its configs after the wait
        is refused with an explicit error instead of cancelling something the
        file keeps (F4).

        Args:
            timeout (float): Seconds to wait for the graceful stop before
                escalating to kill. None waits forever

        Returns:
            tuple[bool, List[str]]: Whether the restart may continue, and the
                configs to resume after it = the workers whose state is
                "restarting" when the wait ends (sorted). A worker the user
                stopped (default kill, no restart_resume) is not in it. A
                cancelled wait carries no resume list ((False, [])). A wait
                starting after restart_cancel() released the run reports the
                same cancellation
        """
        run = self._restart
        if run is None:
            # a cancel released the run before this wait started: report it
            # like any other cancelled wait, nothing was frozen
            return False, []
        deadline = None if timeout is None else time.monotonic() + timeout

        # 1) graceful wait: until every worker stopped (return), the wait was
        #    cancelled (return) or the timeout ended it (escalate below)
        while True:
            with self._lock:
                remaining = self._restart_pending_configs_locked()
            if not remaining:
                # every worker stopped: the resume list is final from here on
                # (the freeze re-checks the abort in its own critical section)
                return self._freeze_restart_resume_list(run)
            if run.abort.is_set():
                # cancelled: never write a resume file and never restart
                return False, []
            if deadline is not None and time.monotonic() >= deadline:
                break
            # wait on the abort event: a cancel wakes the loop immediately,
            # otherwise the poll does not outlive the poll interval
            run.abort.wait(RESTART_WAIT_POLL)

        # 2) the timeout is over: the workers still running did not stop by
        #    themselves, end them (restart_resume=True keeps their resume intent)
        logger.info(
            f'[WorkerManager] Graceful stop timeout ({timeout}s), '
            f'killing workers: {", ".join(remaining)}'
        )
        for config in remaining:
            self.worker_kill(config, restart_resume=True)

        # 3) wait for the kills: no deadline any more, the workers are being
        #    terminated (a kill of a worker still spawning lands when it boots)
        while True:
            with self._lock:
                remaining = self._restart_pending_configs_locked()
            if not remaining:
                return self._freeze_restart_resume_list(run)
            if run.abort.is_set():
                # cancelled while the kills were running
                return False, []
            run.abort.wait(RESTART_WAIT_POLL)

    def restart_cancel(self) -> None:
        """
        Cancel the graceful restart in progress (idempotent)

        Sets the abort event (a blocking restart_wait() returns early with
        (False, []), no resume list and nothing frozen), releases the run
        (the restarting gate and the frozen resume list of its transaction go
        with it), drops every pending_restart mark and returns the process-less
        "restarting" / "resuming" entries to idle (removed from the state
        dict). Workers still stopping (scheduler-stopping / killing) only lose
        their marks: they stop through their normal path to idle and are not
        resumed.
        """
        run = self._restart
        if run is not None:
            run.abort.set()
        with self._lock:
            self._restart = None
            for state in list(self.state.values()):
                if state.pending_restart:
                    state.pending_restart = False
                if state.state in ['restarting', 'updating', 'resuming']:
                    self._set_state(state, 'idle')

    def _restart_pending_configs_locked(self) -> 'List[str]':
        """
        Configs the graceful restart wait covers (lock required)

        A worker counts as stopped when its entry is gone (idle) or its state
        is idle / error / restarting / updating; "disconnected" is transient
        (the disconnect handler is finishing its cleanup) and keeps the wait
        going.

        Returns:
            List[str]: Sorted config names
        """
        return sorted(
            config
            for config, state in self.state.items()
            if state.state not in ['idle', 'error', 'restarting', 'updating']
        )

    def _freeze_restart_resume_list(
        self, run: 'RestartRun'
    ) -> 'tuple[bool, List[str]]':
        """
        Freeze the resume list of the finished wait and report the wait result

        Called by restart_wait() when it observed that every worker stopped.
        The observation takes the lock on its own, so the abort is re-checked
        here, in the section the freeze (and the stop routing) runs in: a
        restart_cancel() landing in between wins, nothing is frozen and the wait
        reports the cancellation (the transaction is gone and the cancel path
        owns the cleanup). On success the frozen list and the returned one are
        the same, taken in the critical section the stop routing also takes: a
        stop request either lands before -- and leaves the config out of the
        list -- or is refused.

        Returns:
            tuple[bool, List[str]]: (True, the frozen resume list) when the
                restart may continue, (False, []) when the wait was cancelled

        Args:
            run (RestartRun): The restart this wait belongs to
        """
        with self._lock:
            # a cancel landing in the meantime wins: nothing is frozen and the
            # caller must not continue with the restart
            if run.abort.is_set():
                return False, []
            resume_list = sorted(
                config
                for config, state in self.state.items()
                if state.state in WORKER_PARKED_STATE
            )
            # the frozen list is exactly the returned one: the orchestration
            # writes the resume file from it, and a start accepted through a
            # window from now on could never be resumed (it is refused)
            run.resume_frozen = set(resume_list)
            run.frozen = True
            return True, resume_list

    # ---------------- auto-resume queue (new backend) ----------------

    def mark_resume(self, configs) -> 'List[str]':
        """
        Queue configs for auto-resume after the backend restart (new backend)

        Creates one "resuming" entry per still-idle config: no process, but the
        entry stays in the state dict, so the config is visibly queued and
        cannot be started twice. Configs already started (the user started them
        before the queue reached them) are skipped.

        The entries are the resume intent: a graceful restart that begins while
        they wait (restart_begin) re-collects them into its own resume list, so
        the caller should mark as early as it knows the configs.

        Args:
            configs (list[str]): Config names recorded in the resume file

        Returns:
            List[str]: Actually queued configs, in input order; empty when a
                graceful restart is in progress (the queue is refused, the
                manager is restarting: the marks of this call were not created)
        """
        queued = []
        with self._lock:
            if self.restarting:
                # the manager stopped accepting resumes: a graceful restart owns
                # the backend and collects the marks itself. Creating "resuming"
                # entries now would leave configs that no restart converts and
                # that only stall the restart wait through its timeout
                logger.warning(
                    '[WorkerManager] Resume queue refused: '
                    'a graceful restart is in progress'
                )
                return queued
            for config in configs:
                state = self.state.get(config, None)
                if state and state.state not in ['idle', 'error']:
                    # already started / stopped by the user: skip
                    continue
                if not state:
                    state = WorkerState(mod='', config=config, state='idle')
                    self.state[config] = state
                self._set_state(state, 'resuming')
                queued.append(config)
        return queued

    def drop_resume(self, configs) -> 'List[str]':
        """
        Drop configs from the auto-resume queue (new backend)

        The caller gives up on these configs (the config scan never exposed
        them, or the queue failed): their "resuming" entries are cancelled
        (back to idle, removed), so the config can be started by hand again.
        Only entries still waiting to be started are dropped -- an entry a
        graceful restart already collected is "restarting" and its intent
        belongs to that restart, and a config the user started or cancelled is
        not the caller's to touch (the entry is gone or has a process).

        Args:
            configs (list[str]): Config names to drop from the queue

        Returns:
            List[str]: Configs actually dropped, in input order
        """
        dropped = []
        with self._lock:
            for config in configs:
                state = self.state.get(config, None)
                if state is None or state.state != 'resuming':
                    continue
                self._set_state(state, 'idle')
                dropped.append(config)
        if dropped:
            logger.info(
                f'[WorkerManager] Resume queue entries dropped: {", ".join(dropped)}'
            )
        return dropped

    def worker_resume(
        self, mod: str, config: str, project_root='', mod_root='', path_main=''
    ) -> 'tuple[bool, str]':
        """
        Start a worker queued by mark_resume(), like a manual start

        Args:
            mod (str): Mod name, same shape as worker_start()
            config (str): Config name
            project_root (str): Project root, same as worker_start()
            mod_root (str): Mod root, same as worker_start()
            path_main (str): Mod main entry, same as worker_start()

        Returns:
            whether success, reason
        """
        with self._lock:
            state = self.state.get(config, None)
            if not state or state.state != 'resuming':
                # cancelled by the user, started by someone else, or converted
                # to "restarting" by a new maintenance flow
                return False, f'Worker is not awaiting auto-resume: "{config}"'
            if self.restarting or RESTART_MANAGER.frozen:
                # a flow took the backend over (or the process is being
                # replaced) while the queue was draining: starting now would
                # only be killed at the backend exit and lost
                return False, f'Backend is restarting, cannot resume now: "{config}"'
            # mark immediately
            state.mod = mod
            child_conn = self._mark_starting_locked(state)

        self.on_worker_info(config, f'[WorkerManager] Resuming worker: {config}')
        return self._worker_start_process(
            state, mod, config, child_conn, project_root, mod_root, path_main
        )

    def worker_wait_started(self, config: str, timeout: float) -> 'tuple[bool, str]':
        """
        Wait for a worker of its spawn window to report itself

        worker_start() and worker_resume() return as soon as the process is
        spawned: the entry stays "starting" until the worker announces a state
        of its own through its pipe (its bridge sends "running" once it is up,
        before the mod is imported, which is the earliest moment the process
        exists for the manager) or the manager finalizes the entry another way
        (a spawn failure, a disconnect, a maintenance flow stopping the workers
        of a start still in flight). The wait blocks the calling thread, never
        the backend loop: the resume queue calls it from a worker thread.

        Every transition of the entry wakes the wait, so an entry finalized
        without a report of the worker is seen the moment it happens: the
        timeout only ends a wait whose entry stays in its spawn window without
        the worker ever reporting itself.

        Args:
            config (str): Config name
            timeout (float): Seconds to wait for the entry to leave "starting"

        Returns:
            bool: True when the worker reported a state of its own
                ("running" / "scheduler-waiting"), False when the entry left
                the spawn window another way or the wait expired
            str: The state of the entry at the end of the wait
        """
        deadline = time.monotonic() + timeout
        with self._lock:
            state = self.state.get(config, None)
            if not state:
                return False, 'idle'
            changed = state.changed_event
            changed.clear()
            current = state.state
        while current == 'starting':
            # the deadline is the only end left for an entry that sits in its
            # spawn window while its worker never reports
            if not changed.wait(max(deadline - time.monotonic(), 0.0)):
                break
            with self._lock:
                # read the state and clear the event in one lock hold: a state
                # set in between is seen by this read, a later one by the wait
                # above, never lost
                current = state.state
                changed.clear()
        return current in WORKER_STATE_ALLOWS, current

    # ---------------- maintenance flows (restart / update / daily) ----------------

    def set_park_state(self, state: WORKER_PARK_STATE):
        """
        Set the state the workers stopped by the flow in flight are parked in
        (the flow calls this before restart_begin()).

        Args:
            state (WORKER_PARK_STATE): 'updating' or 'restarting'
        """
        with self._lock:
            self.park_state = state

    def restart_abort(self) -> None:
        """
        Wake the graceful wait in flight without releasing the run

        The cancel of a flow (cancel_restart / cancel_update) ends the wait
        this way: the wait returns its cancellation and the wrap-up of the flow
        releases the run (restart_cancel) and resumes the workers it stopped.
        Idempotent.
        """
        run = self._restart
        if run is not None:
            run.abort.set()

    def parked_configs(self) -> 'List[str]':
        """
        The configs stopped for the maintenance flow in flight (the workers
        parked in 'restarting' / 'updating')

        Must run in a worker thread (the caller uses trio.to_thread): the lock
        is held for the scan.

        Returns:
            List[str]: Sorted config names
        """
        with self._lock:
            return sorted(
                config
                for config, state in self.state.items()
                if state.state in WORKER_PARKED_STATE
            )

    def resume_intent(self) -> 'List[str]':
        """
        The configs queued for auto-resume right now (the entries visible as
        "resuming": the configs a resume file recorded and the starts accepted
        while a flow owned the backend)

        Must run in a worker thread (the caller uses trio.to_thread): the lock
        is held for the scan.

        Returns:
            List[str]: Sorted config names
        """
        with self._lock:
            return sorted(
                config
                for config, state in self.state.items()
                if state.state == 'resuming'
            )

    def _queue_update_start_locked(self, mod, config) -> 'tuple[bool, str]':
        """
        Accept a start request as a queued resume while a maintenance flow owns
        the backend (lock required, see worker_start)

        The caller sees a success and no error: the frontend shows the config
        as "resuming" (Worker topic) and the config starts automatically when
        the flow's wrap-up or the resume queue of the new backend reaches it,
        without a second click.

        Returns:
            whether success, reason
        """
        state = self.state.get(config, None)
        if state is not None:
            if state.state in ['resuming', 'restarting', 'updating']:
                # already queued by this flow or by a restart: accepted, the
                # entry is not created twice
                state.mod = mod
                return True, (
                    f'Worker is queued for auto-resume, it starts when the '
                    f'maintenance ends: "{config}"'
                )
            if state.state not in ['idle', 'error']:
                return (
                    False,
                    f'Worker is already running: "{config}", state="{state.state}"',
                )
        run = self._restart
        if run is not None and run.frozen:
            # the resume list is frozen and its file is written from it: an
            # entry queued now could never be resumed, the start is refused
            # instead of being lost silently
            return False, (
                f'The backend is past its point of no return and restarts now, '
                f'start the config after the restart: "{config}"'
            )
        if state is None:
            state = WorkerState(mod=mod, config=config, state='idle')
            self.state[config] = state
        state.mod = mod
        if run is not None:
            # the flow already stopped the workers: the entry is parked and
            # restart_wait() collects it into the resume list the handover
            # writes
            state.pending_restart = True
            self._set_state(state, self.park_state)
        else:
            # the flow has not stopped the workers yet: the entry waits as a
            # queued resume, stop_all collects the "resuming" entries into its
            # resume list
            state.pending_restart = False
            self._set_state(state, 'resuming')
        self.on_worker_info(
            config, f'[WorkerManager] Start queued by the maintenance flow: {config}'
        )
        return True, (
            f'Worker is queued for auto-resume, it starts when the maintenance '
            f'ends: "{config}"'
        )

    def close(self):
        """
        Terminate all workers and release resources
        """
        # Remove self from singleton cache, so the next access will have a new manager
        self.__class__.singleton_clear()

        while 1:
            with self._lock:
                states = list(self.state.values())
                if not states:
                    break
                self.state.clear()
                logger.info(
                    f'[WorkerManager] Closing manager, remaining {len(states)} workers'
                )
                for state in states:
                    self._set_state(state, 'killing')

            # Terminate processes
            for state in states:
                state.process_terminate()

            # Wait for processes
            for state in states:
                state.process_join(timeout=1)
                state.process_kill(timeout=1)

            # Close connections
            for state in states:
                state.conn_close()

            # Wait for threads
            for state in states:
                if state.recv_thread is not None and state.recv_thread.is_alive():
                    state.recv_thread.join(timeout=1)

            with self._lock:
                for state in states:
                    state.process = None
                    state.recv_thread = None
                    self._set_state(state, 'idle')
            # maybe new worker started while we are killing existing workers

        logger.info('[WorkerManager] All closed')
