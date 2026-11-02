"""
The scheduler topics: TaskQueue, TaskRunning and TaskQueueI18n.

Ported from alasio/backend/topic/que.py (703 lines). Two of the three topics
have no producer in OAS, so they publish empty data by construction; the
deviations that matter:

- the task table has no producer. Upstream builds it from the Mod domain
  object (``mod.get_task_schedule(config)``, which splits the disk schedule
  table by the wall clock: ``NextRun <= now`` is pending, later is waiting).
  OAS has neither a Mod domain class nor a schedule API -- ``oas/mod/adapter.py``
  still stubs ``queue_index_data`` -- so ``TaskQueueSource.on_init`` publishes
  the empty table ``{'pending': [], 'waiting': []}``. Worker pushes
  (``ConfigEvent(t='TaskQueue')``) are still merged exactly as upstream, so a
  worker that publishes a table is displayed;
- the time-driven refresh manager (upstream ``TaskQueueUpdateManager``, 250
  lines) is not ported. It exists to recompute the table when a waiting task's
  NextRun passes and to answer the config-save refresh requests for it -- both
  are about the schedule OAS cannot read. Without a table there is nothing to
  recompute, so the ``subscribe`` / ``unsubscribe`` / ``on_event`` / ``reinit``
  overrides that published the next refresh to that manager are dropped with
  it, and so are ``next_waiting_time`` and the ``on_config_event`` /
  ``_need_reinit`` pair (their only purpose was to feed the manager);
- the i18n table has no source. Upstream reads it from the Mod
  (``MOD_LOADER.get_queue_i18n(mod)``) and resolves the ``{task}.{lang}`` keys
  itself; OAS has no backend i18n layer at all (the backend publishes i18n keys
  and the frontend translates them), so ``TaskQueueI18nSource.on_init`` returns
  the empty table and the frontend falls back to the task names. The framework
  sends no event for an empty snapshot and this topic has no push channel either
  (static disk cache), so a subscriber reads nothing at all;
- ``TaskRunning`` is registered in the /api/ws registry here, unlike upstream,
  which defines the topic in ``que.py`` but leaves it unregistered. Its data
  only arrives through worker pushes (``ConfigEvent(t='TaskRunning')``), so a
  worker that never publishes a running task shows nothing;
- the imports are the OAS ones (``trio`` / ``anyio`` is not needed, no thread
  hop survived the manager) and ``MOD_LOADER`` lives in ``oas.mod.loader``.
"""

from typing import TypedDict

from msgspec import NODEFAULT, ValidationError, convert

from oas.backend.reactive.event import ResponseEvent
from oas.backend.reactive.source import (
    ConfigSource,
    DiskCache,
    DiskCachePush,
    KeyedSource,
    ResidentCache,
)
from oas.backend.topic.state import ConnState
from oas.backend.ws.ws_topic import BaseTopic
from oas.config.entry.model import TaskItem
from oas.logger import logger


class TaskQueueData(TypedDict):
    """
    The task table of one config, split by the wall clock.

    ``pending`` holds the tasks whose ``NextRun`` has passed, ``waiting`` the
    ones still ahead -- upstream ``mod.get_task_schedule`` does that split.
    """

    pending: list[TaskItem]
    waiting: list[TaskItem]


class TaskQueueSource(ConfigSource, DiskCachePush):
    """
    Task queue cache source: disk cache + event push (config-keyed).

    Data = ``{pending, waiting}``, the empty table in OAS (see the module
    docstring), kept up to date by worker TaskQueue events. Event protocol:
    ``ConfigEvent(t='TaskQueue')`` with ``v`` a dict of any subset of
    ``{pending, waiting}`` -- merged key by key. Increments are keyed set
    patches of the changed keys (the client merges them into the task table);
    full events carry the whole data at the root.

    Data shape: data is ALWAYS a ``TaskQueueData`` (``TaskItem`` items). The
    read path builds them by construction, and a push payload is decoded into
    ``TaskItem`` before it is merged (msgspec decodes the worker bytes with
    ``v: Any``, so the raw items are plain dicts) -- a payload that does not
    decode is dropped with a warning, never stored raw. Consumers therefore
    never deal with the dict shape, and an identical push compares equal to the
    read table.

    Lifecycle: DiskCachePush -- worker events refresh the data TTL; the
    data-expiry GC recycles the instance only when the TTL expired AND no
    subscriber is attached (the push channel is bound to the instance).
    """

    TOPIC_NAME = 'TaskQueue'
    TTL = 5
    data: TaskQueueData

    def on_init(self):
        """
        [线程] Build the task table.

        OAS has no schedule source (see the module docstring), so this is the
        empty table: the topic stays empty until the Mod facade exposes the
        schedule upstream reads here. Never touches ``self.data``
        (cross-thread).

        Returns:
            dict: ``{'pending': [], 'waiting': []}`` -- empty lists, never
                None.
        """
        return {'pending': [], 'waiting': []}

    def _apply(self, event):
        """
        [锁内] Simple merge: each present key of ``{pending, waiting}``
        replaces the corresponding key of data.

        The push payload is decoded into ``TaskItem`` items first: data is a
        ``TaskQueueData`` (see the class docstring), and a decoded list also
        compares equal to the read one, so an identical push does not
        broadcast. A key that does not decode is dropped with a warning -- a
        foreign shape is a protocol bug, it must never enter data.

        Args:
            event (ConfigEvent): Worker push whose ``v`` is a dict of any
                subset of ``{pending, waiting}``

        Returns:
            bool: If data changed
        """
        value = event.v
        modified = False
        for key in ['pending', 'waiting']:
            if key not in value:
                continue
            after = self._decode(value[key])
            if after is None:
                continue
            before = self.data.get(key, NODEFAULT)
            # stop broadcast if not modified
            if before != after:
                self.data[key] = after
                modified = True
        return modified

    @staticmethod
    def _decode(value):
        """
        [锁内] ``TaskItem`` items of a push payload value.

        Args:
            value (list): pending / waiting value of a worker push (msgspec
                decodes the ConfigEvent payload with ``v: Any``, so the items
                are plain dicts here)

        Returns:
            list[TaskItem] | None: None when the value is not a task list (the
                caller drops it: data only ever holds ``TaskQueueData``)
        """
        try:
            return convert(value, list[TaskItem])
        except (ValidationError, TypeError) as e:
            logger.warning(f'[TaskQueue] Malformed task table payload ignored: {e}')
            return None

    def _convert(self, event):
        """
        [锁内] Keyed set patches of the event's changed keys, referencing the
        applied values.

        The worker event ``v`` is a dict of any subset of ``{pending,
        waiting}``; each key is forwarded as a separate keyed set so the client
        merges the patch instead of replacing the whole task table. Values are
        the applied ones (``data[key]``, set by ``_apply`` in this same
        critical section): they are bound into data by replacement and never
        mutated in place afterwards, so encoding later (outside the lock) is
        safe. Unknown payload keys are not forwarded -- ``_apply`` ignores
        them, the client table only has the two keys.

        Args:
            event (ConfigEvent): Worker push, see ``_apply``

        Returns:
            list[ResponseEvent]: One keyed set per changed key
        """
        value = event.v
        return [
            ResponseEvent(t=self.TOPIC_NAME, o='set', k=(key,), v=self.data[key])
            for key in ['pending', 'waiting']
            if key in value
        ]


class TaskQueue(BaseTopic):
    """
    The task queue of the selected config: ``{pending, waiting}`` task lists

    Subscribing registers the source of the connection's config and builds the
    table through ``on_init`` (the empty table in OAS).
    """

    TOPIC_NAME = 'TaskQueue'

    async def get_source(self):
        """
        Data preparation: reinit (TTL / dirty no-op when fresh; the first
        subscription of a config without worker events fills the task table
        through on_init).

        Returns:
            TaskQueueSource | None: The source of the current config, None when
                no config is selected.
        """
        state = ConnState(self.conn_id, self.server)
        config_name = await state.config_name
        if not config_name:
            return None
        source = TaskQueueSource(config_name)
        await source.reinit()
        return source


class TaskRunningSource(ConfigSource, ResidentCache):
    """
    Current running task of a config, resident (event stream only).

    Event protocol: ``ConfigEvent(t='TaskRunning')`` with ``v`` = task_name |
    None -- sent by the worker scheduler on every task switch. data is the task
    name itself (None = no task running). There is no full-data source: every
    change flows through events, so reinit is never called (the get_source of
    the topic does not call it). Runtime-produced state is kept resident: a
    later front-end visit finds the current task without events having to be
    replayed.

    ``data`` starts as None (upstream identical) and the framework sends no
    event for an empty snapshot, so a subscriber reads nothing until the first
    worker push: "no task running" is silence, not a ``None`` payload.
    """

    TOPIC_NAME = 'TaskRunning'

    def __init__(self, config_name):
        super().__init__(config_name)
        # no running task until the first scheduler event
        self.data = None

    def _apply(self, event):
        """
        [锁内] Replace the running task.

        Args:
            event (ConfigEvent): Worker push with ``v`` = task name | None

        Returns:
            bool: If data changed
        """
        value = event.v
        if self.data == value:
            return False
        self.data = value
        return True

    def _convert(self, event):
        """
        [锁内] Event -> root set of the running task.

        Args:
            event (ConfigEvent): Worker push, see ``_apply``

        Returns:
            ResponseEvent: The root set carrying the whole running value
        """
        return ResponseEvent(t=self.TOPIC_NAME, o='set', v=self.data)


class TaskRunning(BaseTopic):
    """
    The task the worker scheduler is running right now for the selected config

    Pure event-stream topic: subscribing registers the resident source of the
    config, whose in-memory value is the full event.
    """

    TOPIC_NAME = 'TaskRunning'

    async def get_source(self):
        """
        Pure event-stream source: no reinit (there is no full-data read; the
        full is the in-memory data snapshot of subscribe).

        Returns:
            TaskRunningSource | None: The source of the current config, None
                when no config is selected.
        """
        state = ConnState(self.conn_id, self.server)
        config_name = await state.config_name
        if not config_name:
            return None
        return TaskRunningSource(config_name)


class TaskQueueI18nSource(KeyedSource, DiskCache):
    """
    One-shot disk-cache source of TaskQueueI18n: key (mod_name, lang).

    Static i18n content; no push after the full snapshot. Recycled by the
    data-expiry GC when the data TTL expired, regardless of subscribers
    (DiskCache semantics). The table is empty in OAS, see the module docstring.
    """

    TOPIC_NAME = 'TaskQueueI18n'

    def __init__(self, mod_name, lang):
        super().__init__()
        self.mod_name = mod_name
        self.lang = lang

    def on_init(self):
        """
        Build the task i18n table of the mod.

        OAS publishes i18n keys and lets the frontend translate them, so there
        is no table to read: the empty one makes the frontend fall back to the
        raw task names.

        Returns:
            dict[str, str]: Always empty in OAS.
        """
        return {}


class TaskQueueI18n(BaseTopic):
    """
    The i18n table of the task queue, keyed by task name

    Subscribing registers the source of the connection's (mod, lang) and builds
    the table (empty in OAS).
    """

    TOPIC_NAME = 'TaskQueueI18n'

    async def get_source(self):
        """
        Data preparation: reinit (the first subscription reads the table
        through on_init).

        Returns:
            TaskQueueI18nSource | None: The source of the current (mod, lang),
                None when no mod or language is selected.
        """
        state = ConnState(self.conn_id, self.server)
        mod_name = await state.mod_name
        lang = await state.lang
        if not mod_name or not lang:
            return None
        source = TaskQueueI18nSource.get(mod_name, lang)
        await source.reinit()
        return source
