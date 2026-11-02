"""
The worker state source and the backend worker manager of the Worker topic.

Ported from alasio/backend/topic/_worker.py. Deviations, all recorded in
oas/backend/README.md:

- the restart / resume half of the manager is not ported (park states, the
  resume queue, worker_resume), see oas/backend/worker/manager.py;
- the preview notification (``PreviewTask.on_worker_state``) is not ported:
  the Preview topic has no producer here yet. Upstream schedules it on the
  trio loop with ``GLOBAL_CONTEXT.trio_token.run_sync_soon``, the equivalent
  wakeup in OAS is ``AnyIO.call_soon``, which lands together with the topic;
- the config event router keeps the ``Log`` / ``Worker`` / ``ConfigArg``
  branches. ``ConfigArg`` routes into the unified config-save entry
  (``oas/backend/topic/_config_event.py``), so a config saved from the worker
  side reaches the GUI view sources like one saved through an RPC. The
  ``Preview`` / ``TaskQueue`` / ``TaskRunning`` branches need the topics that
  are not ported yet; each branch is added with its own topic, until then an
  unknown topic is warned about as upstream does;
- ``Mod`` (alasio.config.entry.mod) becomes ``ModEntryInfo``: OAS has no Mod
  domain class, and ``BackendWorkerManager`` unpacks exactly the three fields
  it needs (``name`` / ``root`` / ``path_main``).
"""

from oas.backend.reactive.event import ResponseEvent
from oas.backend.reactive.source import GlobalSource, ResidentCache
from oas.backend.topic import _config_event
from oas.backend.topic.log import LogCache
from oas.backend.worker.event import ConfigEvent
from oas.backend.worker.manager import WORKER_STATE, WorkerManager
from oas.ext import env
from oas.logger import logger
from oas.mod.info import ModEntryInfo


class WorkerSource(GlobalSource, ResidentCache):
    """
    Worker states of every config: data = dict[config, WORKER_STATE],
    resident (runtime-produced state kept for later front-end visits).

    Event protocol: on_event((config, state)); 'idle' deletes the config
    (absent workers default to idle), any other state is set. There is no
    full-data source: every state transition goes through
    WorkerManager.on_worker_state -> WorkerSource().on_event, so the data is
    always up to date, also without subscribers.
    """

    TOPIC_NAME = 'Worker'

    def _apply(self, event):
        config, state = event
        if state == 'idle':
            if config not in self.data:
                return False
            del self.data[config]
        else:
            if self.data.get(config, None) == state:
                return False
            self.data[config] = state
        return True

    def _convert(self, event):
        config, state = event
        if state == 'idle':
            return ResponseEvent(t=self.TOPIC_NAME, o='del', k=(config,))
        return ResponseEvent(t=self.TOPIC_NAME, o='set', k=(config,), v=state)


class BackendWorkerManager(WorkerManager):
    def worker_start(self, mod: ModEntryInfo, config: str) -> 'tuple[bool, str]':
        project_root = env.PROJECT_ROOT
        mod_root = mod.root
        path_main = mod.path_main
        return super().worker_start(
            mod=mod.name,
            config=config,
            project_root=project_root,
            mod_root=mod_root,
            path_main=path_main,
        )

    def worker_resume(self, mod: ModEntryInfo, config: str) -> 'tuple[bool, str]':
        """
        Start a worker queued by mark_resume(), like worker_start()
        """
        project_root = env.PROJECT_ROOT
        mod_root = mod.root
        path_main = mod.path_main
        return super().worker_resume(
            mod=mod.name,
            config=config,
            project_root=project_root,
            mod_root=mod_root,
            path_main=path_main,
        )

    def on_worker_state(self, config: str, state: WORKER_STATE):
        # Worker state source: locked forwarding, safe from any thread
        # (worker recv thread / anyio RPC thread / to_thread).
        WorkerSource().on_event((config, state))

    def on_config_event(self, event: ConfigEvent):
        topic = event.t
        if topic == 'Log':
            # cache and broadcast log
            cache = LogCache(event.c)
            cache.on_event(event)
        elif topic == 'Worker':
            self.on_worker_state(config=event.c, state=event.v)
        elif topic == 'ConfigArg':
            # unified entry of config-save events (viewport dispatch +
            # TaskQueue linkage), replaces the old msgbus broadcast
            _config_event.on_config_event(event.c, event.v)
        else:
            logger.warning(f'Unknown topic event: {topic}')


BACKEND_WORKER_MANAGER = BackendWorkerManager()
