import threading
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Optional

import trio
from msgspec.json import Encoder

from oas.backend.reactive.event import ResponseEvent
from oas.ext.singleton import Singleton, SingletonKeyed, SingletonNamed
from oas.logger import logger

if TYPE_CHECKING:
    from trio._core import TrioToken

    from oas.backend.ws.ws_topic import BaseTopic

ENCODER = Encoder()

# Classes whose instances may be garbage-collected when data expires
# (see BaseSource.gc_idle). Collected on class definition via
# __init_subclass__: a class joins the list only when it declares GC=True
# with a numeric TTL -- the GC switch is static, decided once at class
# creation, never at runtime.
_GC_CLASSES: "set[type]" = set()

# Framework layers of the source hierarchy (known, fixed set): never
# instantiated on their own, they leave TOPIC_NAME to the concrete
# business sources below them. The class-level TOPIC_NAME check in
# __init_subclass__ exempts this list by name; add any new framework
# layer here (a missing entry surfaces as a class-definition warning).
# GuiConfigSource (topic/_gui_config.py) is the application-level shared
# base of the config view sources and is exempt the same way.
_FRAMEWORK_LAYERS = frozenset((
    'EventSource',
    'ResidentCache',
    'DiskCache',
    'DiskCachePush',
    'GlobalSource',
    'ConfigSource',
    'KeyedSource',
    'NoCachePush',
    'GuiConfigSource',
))


class BaseSource:
    """
    Source protocol: event stream + subscriber set of a topic.

    Thread model:
    - on_event()    can be called from any thread (worker recv thread /
                    Trio thread / any backend thread), thread safe.
    - subscribe()   can only be called in the Trio thread, async
                    (contains no blocking await).
    - unsubscribe() can only be called in the Trio thread, sync.
    - reinit() / fetch_init() are Trio-only, default empty.

    Iron rule: never await inside a lock. All critical sections are
    synchronous in-memory operations.

    A source is built by composing two orthogonal dimensions:
    - dimension A (registry shape, see GlobalSource / ConfigSource /
      KeyedSource): where the instances live, how they are fetched,
      enumerated and removed;
    - dimension B (cache / push model, see EventSource and its semantic
      subclasses ResidentCache / DiskCache / DiskCachePush, plus
      NoCachePush): where the data comes from, how long it is cached,
      what subscribing means.
    Concrete topics combine them through inheritance, e.g.
    class TaskQueueSource(ConfigSource, DiskCachePush).

    Subscriber contract: every subscriber (a ws BaseTopic) must implement
    deliver(payload) -- the sync entry the source broadcasts increments
    through. Delivery backpressure is the subscriber's own business (the
    topic queues what its connection cannot take and sends it with await
    send, see BaseTopic.deliver); the source itself never blocks.
    """

    # Topic name this source feeds: tagged into every full / incremental
    # event (ResponseEvent.t). Every concrete source class must set it;
    # the check runs at class definition time (see __init_subclass__), so
    # a missing TOPIC_NAME is reported on import instead of on the first
    # subscribe.
    TOPIC_NAME = ''
    # Inbox is the cross-thread entry buffer (payload objects).
    # When it overflows, the oldest payload is dropped.
    INBOX_MAXLEN = 1024
    # GC switch: whether instances of this class take part in the data-
    # expiry garbage collection. It is a STATIC class declaration:
    # __init_subclass__ collects GC-enabled classes into _GC_CLASSES once
    # at class definition time and the gc loop never evaluates the flag
    # again at runtime.
    # - GC=True classes are recycled by BaseSource.gc_idle() when their
    #   data TTL expired (the recycle rule of the dimension-B model
    #   applies, see DiskCache / DiskCachePush);
    # - GC=False classes never enter the gc loop: resident sources
    #   (ResidentCache), view sources that remove themselves on the last
    #   unsubscribe (NoCachePush) and process-wide caches whose readers
    #   rely on a stable instance (e.g. ConfigScanSource with GC=False).
    GC = False
    # Recycle of a GC-enabled source additionally requires an empty
    # subscriber set. DiskCachePush sets it: the subscriber channel is
    # bound to the instance, recycling a subscribed instance would cut
    # the push. DiskCache leaves it False: its full never expires, so
    # recycling a subscribed instance is harmless (see the class docs).
    GC_NEEDS_NO_SUBSCRIBER = False
    # Data freshness window of the cache models (seconds | None):
    # - fetch_init re-reads the full data when the window expired;
    # - the idle GC removes the instance when the window expired
    #   (only for GC=True classes);
    # - None = no window (resident, or read on every fetch);
    # - the cache models set their own default: DiskCache / DiskCachePush
    #   default to 8s (most topics inherit it without declaring TTL); a
    #   subclass overrides the value or sets TTL=None explicitly to
    #   disable the window.
    TTL = None
    # Full data of cache sources (EventSource initializes it per instance).
    # The default subscribe() encodes it under the lock; a source without
    # data (None) registers without a full event. NoCachePush overrides
    # subscribe() entirely and has no data.
    data = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Static GC membership, decided once at class definition time:
        # only classes that opt in (GC=True) with a numeric TTL are
        # collected; the framework layers of this module are exempt by
        # name (see _FRAMEWORK_LAYERS -- they never hold instances).
        # There is deliberately no runtime flag check in the gc loop --
        # ConfigScan-like classes just declare GC=False.
        if cls.GC and cls.TTL is not None and cls.__name__ not in _FRAMEWORK_LAYERS:
            _GC_CLASSES.add(cls)
        else:
            _GC_CLASSES.discard(cls)
        # TOPIC_NAME must be set on every concrete source class (checked
        # at class definition time); the framework layers of this module
        # are exempt by name (see _FRAMEWORK_LAYERS above).
        if cls.__name__ not in _FRAMEWORK_LAYERS and not cls.TOPIC_NAME:
            logger.warning(f'{cls.__name__}.TOPIC_NAME is not set')

    def __init__(self):
        # One lock covers data (cache sources) and the inbox. The
        # subscriber set is only touched from the Trio thread; the lock
        # just keeps it atomic with the snapshot.
        self._lock = threading.Lock()
        self._subscribers: "set[BaseTopic]" = set()
        # Cross-thread entry buffer written by on_event (any thread) and
        # reinit (Trio), drained by _sync_to_trio in one batch.
        self._inbox: "deque[ResponseEvent]" = deque(maxlen=self.INBOX_MAXLEN)
        # Set on the first subscribe (Trio thread); _ring relies on it.
        self._trio_token: "Optional[TrioToken]" = None

    # ---------------- subscribe / unsubscribe ----------------

    async def subscribe(self, sub) -> "Optional[bytes]":
        """
        [Trio] Register a subscriber and return the encoded full snapshot.

        - Cache sources: register first, then encode the current data
          under the lock (the payload may reference data, frozen while
          the lock is held).
        - Empty data returns None (no full event, matching the previous
          EventCache behavior).
        - Sources without data (self.data is None) register silently.
        - After registration the instance reconciles with its registry
          (dimension A hook): when a concurrent GC removed it while the
          get_source() -> subscribe() flow was in flight, it re-registers
          itself -- a live subscriber means the instance is wanted again
          (see _reconcile).

        Ordering contract: after subscribe() returns, the caller must send
        the returned bytes with send_nowait() without any await in between,
        so the full event is enqueued before any later increment.
        """
        with self._lock:
            if self._trio_token is None:
                self._trio_token = trio.lowlevel.current_trio_token()
            self._subscribers.add(sub)
            data = self.data
            if not data:
                payload = None
            else:
                # Encode under the lock: the payload references data, and
                # data cannot be modified while the lock is held.
                payload = ENCODER.encode(ResponseEvent(t=self.TOPIC_NAME, o='full', v=data))
        self._reconcile()
        return payload

    def unsubscribe(self, sub):
        """
        [Trio] Unsubscribe. Idempotent.
        """
        with self._lock:
            self._subscribers.discard(sub)

    def _reconcile(self):
        """
        [Trio，锁外] Registry reconciliation after registration.

        Dimension A hook (default: no registry): a concurrent GC may have
        removed this instance while get_source() -> subscribe() was in
        flight. With a live subscriber the instance is wanted again:
        re-register it when its registry slot is vacant; when a newer
        instance already occupies the slot, stay unregistered (the
        subscription keeps working through this instance, full already
        sent; the next dependency change rebinds to the newer instance).
        """
        pass

    # ---------------- sub-class hooks ----------------

    async def reinit(self, force=False):
        """
        [Trio] Refresh the full data and broadcast a full event.
        Default empty implementation: sources without a full data source
        (Log / Worker / NoCachePush sources) never call it.
        """
        pass

    async def fetch_init(self, force=False):
        """
        [Trio] Sub-class hook of reinit(): read the latest full data.
        Default empty implementation. May carry a freshness check; returns
        the new data, or None when no update is needed.
        """
        pass

    # ---------------- doorbell and batch delivery ----------------

    def _push(self, payload):
        """
        [任意线程，锁内调用] Enqueue one payload and ring the doorbell.
        """
        was_empty = not self._inbox
        self._inbox.append(payload)
        if was_empty:
            self._ring()

    def _ring(self):
        """
        [任意线程，锁内调用] Wake up the batch delivery on the Trio thread.

        The doorbell rings on "inbox transitions from empty to non-empty",
        so pushing several payloads in one critical section wakes Trio once.
        """
        if self._trio_token is None:
            # No subscriber yet: the token is only set by the first
            # subscribe (Trio thread). Sources without subscribers only
            # apply events, never schedule anything.
            return
        try:
            self._trio_token.run_sync_soon(self._sync_to_trio)
        except trio.RunFinishedError:
            pass  # event loop already shut down

    def _sync_to_trio(self):
        """
        [Trio 线程] run_sync_soon callback: drain the inbox in one batch,
        encode once, deliver to every subscriber. Not a coroutine.
        """
        with self._lock:
            if not self._inbox:
                # Several doorbells may be scheduled while the first one is
                # running; empty runs are safe no-ops.
                return
            # Copy the batch under the lock, then clear: every append path
            # (on_event / reinit) holds the same lock, so no producer can
            # interleave between the copy and the clear -- the batch is
            # exactly the queued events and nothing is left for a
            # duplicate delivery.
            batch = list(self._inbox)
            self._inbox.clear()
        # Encode outside the lock: payloads are frozen inside the lock
        # (see the freeze rules of EventSource), so encoding is safe.
        if len(batch) == 1:
            payload = ENCODER.encode(batch[0])
        else:
            # Merge the batch into one array message, encoded once.
            payload = ENCODER.encode(batch)
        # Deliver to every subscriber. The backpressure strategy is the
        # subscriber's own business: each topic buffers what its
        # connection cannot take yet (per-subscription outbox,
        # BaseTopic.deliver) and sends it with await send when the send
        # buffer frees a slot. The source never blocks: send_nowait
        # fails fast and the topic takes over, so a slow connection never
        # delays the delivery to fast ones.
        self._deliver_all(payload)

    def _deliver_all(self, payload):
        """
        [Trio 线程] Deliver one encoded payload to every current
        subscriber. No lock: the subscriber set is only touched from the
        Trio thread, so it cannot change while this runs. Also the
        run_sync_soon target of reinit full deliveries: the FIFO order of
        the callback queue keeps a full event behind the increments
        queued before it.
        """
        for sub in self._subscribers:
            sub.deliver(payload)

    # ---------------- idle GC ----------------

    @classmethod
    def gc_idle(cls):
        """
        [任意线程] Data-expiry garbage collection over all collectable
        source classes. Mounted in sync_task_gc (app.py, one round every
        8s). Membership is static: only classes that declared GC=True with
        a numeric TTL at class definition time are in _GC_CLASSES.

        An instance is removed when its data TTL expired (the recycle
        rule of its dimension-B model applies: DiskCache ignores
        subscribers, DiskCachePush additionally requires an empty
        subscriber set). Thread safety: instance enumeration goes
        through a registry / singleton snapshot (never mutate the dict
        while iterating), the freshness timestamp (and subscriber set of
        the keep-on-subscriber models) are read under the instance lock.
        """
        for src_cls in list(_GC_CLASSES):
            try:
                cls._gc_idle_class(src_cls)
            except RuntimeError:
                # registry mutated concurrently by the Trio thread;
                # skip this class and retry on the next round
                continue

    @classmethod
    def _gc_idle_class(cls, src_cls):
        now = time.monotonic()
        for inst in src_cls._iter_idle_instances():
            if type(inst) is not src_cls:
                # intermediate class in the collection: instances are
                # collected under their own concrete class
                continue
            with inst._lock:
                if inst._subscribers and inst.GC_NEEDS_NO_SUBSCRIBER:
                    # keep-on-subscriber model (DiskCachePush): a live
                    # subscriber channel is bound to this instance, never
                    # recycle it
                    continue
                # Freshness base: data activity since the last fetch /
                # event; _lastrun starts at the creation moment, so a
                # brand-new instance is protected for TTL from its birth
                # (see EventSource.__init__).
                if now - inst._lastrun < src_cls.TTL:
                    continue
                # Removal INSIDE the instance lock (lock order: instance
                # lock -> registry lock): the expiry decision and the
                # registry removal are one critical section, atomic
                # against subscriber attach (subscribe registers under
                # the same instance lock and only reconciles with the
                # registry after releasing it). Without this, a
                # subscriber could attach between the decision and the
                # removal and end up stranded on a removed instance:
                # later events would go to a fresh instance and never
                # reach it (see the design doc, 11.5). Deadlock safety:
                # no code path takes a registry lock while holding an
                # instance lock in the reverse direction (registry
                # holders never touch instance locks), so instance ->
                # registry nesting is acyclic.
                inst._remove()

    @classmethod
    def _iter_idle_instances(cls):
        """
        Snapshot the live instances of this class for the data-expiry GC.
        Only implemented by classes with GC=True and a numeric TTL.
        """
        return []

    def _remove(self):
        """
        Unregister this instance from its singleton / registry.
        Called by the data-expiry GC (dimension-A models) or by
        NoCachePush when its last subscriber leaves.
        """
        pass


class EventSource(BaseSource):
    """
    Cache-source implementation layer (dimension B of the source model):
    a full data dict kept fresh by either an event stream (on_event) or a
    full-data source (fetch_init / reinit). The semantic subclasses
    ResidentCache / DiskCache / DiskCachePush are the business models a
    concrete topic picks; EventSource itself is the shared implementation
    and never instantiated on its own.

    Sub-class hooks:
    - on_init() / on_init_async(): read the full data;
    - _apply(event): apply an event under the lock, return whether data
      changed (default False: no event stream);
    - _convert(event): [锁内] build the incremental response(s) of an
      event _apply accepted. Default raises: unreachable without an event
      stream, a missing override with one is a class bug.

    Freeze contract: full events reference data and are encoded INSIDE the
    critical section (subscribe / reinit) -- data may be mutated in place
    by event threads as soon as the lock is released, so a full payload
    never outlives the lock unencoded. Incremental responses are queued as
    objects and encoded later, outside the lock (batch, _sync_to_trio);
    their values must therefore never be mutated after the response is
    built. Referencing the event payload itself is safe: worker events are
    decoded objects bound into data by replacement -- an apply must
    replace a bound container wholesale, never mutate it in place
    afterwards.
    """

    def __init__(self):
        super().__init__()
        self._fetch_lock = trio.Lock()
        self.data: Any = {}
        # Timestamp of the last data refresh (event or full read),
        # initialized to the creation moment: a brand-new instance is
        # protected for TTL from its birth (the data-expiry GC recycles on
        # now - _lastrun >= TTL). _lastrun starts at the creation time and
        # moves forward on every data activity (fetch_init success /
        # on_event applied).
        self._lastrun = time.monotonic()
        # False until data has been loaded at least once (fetch_init
        # success or an applied event): the TTL freshness check of
        # fetch_init only applies to loaded data -- a never-loaded instance
        # must always read on its first reinit, even when the freshness
        # window has not expired since creation.
        self._loaded = False
        # True when an event producer is alive: its data is trusted over the
        # full-data source (fetch_init running trust of TaskQueueSource).
        self._running = False
        # Untrusted disk changes (mark_dirty) not yet consumed by a read:
        # >0 = stale, the next fetch_init bypasses the TTL window. Counting
        # (not bool) lets a read tell "its own mark" from "a mark set while
        # it was reading" (see fetch_init).
        self._dirty = 0

    # ---------------- sub-class hooks ----------------

    def on_init(self):
        """
        Synchronous full-data source. Default returns {}.
        """
        return {}

    async def on_init_async(self):
        """
        Default implementation: run on_init() in a worker thread.
        Disk sources must keep their reads in a thread (file / import IO
        must not block the event loop).
        """
        return await trio.to_thread.run_sync(self.on_init)

    def _apply(self, event):
        """
        [锁内] Apply an event into data. Return whether data changed.
        """
        return False

    def _convert(self, event):
        """
        [锁内] Event -> incremental response(s). Called by on_event only
        after _apply accepted the event (data changed).

        Returns:
            ResponseEvent | list[ResponseEvent]: A single response, or a
                list for multi-key events. May reference the event payload
                (bound by replacement, never mutated afterwards): it is
                encoded later, outside the lock.

        Raises:
            NotImplementedError: A source that accepts events (overrides
                _apply) must convert them. Unreachable for sources without
                an event stream (_apply rejects every event beforehand).
        """
        raise NotImplementedError

    # ---------------- data refresh ----------------

    def mark_dirty(self):
        """
        [任意线程] Mark the data stale: an external change (e.g. a config
        save outside the event stream) may have made the current data
        outdated. The next fetch_init bypasses trust / TTL and re-reads.

        Sources without a full-data source never call it. The mark is
        consumed by a successful read (fetch_init); a read that fails
        keeps it, so the next read retries.
        """
        with self._lock:
            self._dirty += 1

    async def fetch_init(self, force=False):
        """
        [Trio] Read the latest full data.

        - force: ignore the freshness window;
        - dirty (mark_dirty): ignore the freshness window, the disk may
          have changed outside the event stream;
        - the read consumes the dirty marks that existed when it started;
          marks set while the read runs survive it (the result may
          predate them), so they trigger another read.

        Args:
            force (bool): Ignore the freshness window.

        Returns:
            Any | None: The new data, or None when the current data is
                still fresh (reinit skips the broadcast).
        """
        with self._lock:
            if not force and not self._dirty:
                if self.TTL is not None and self._loaded:
                    # Freshness window of loaded data only: a never-loaded
                    # instance (created but not fetched / evented yet) must
                    # always read on its first reinit.
                    if time.monotonic() - self._lastrun < self.TTL:
                        return None
            dirty_before = self._dirty
        new = await self.on_init_async()
        with self._lock:
            self._lastrun = time.monotonic()
            self._loaded = True
            if self._dirty == dirty_before:
                # consumed the marks that existed when the read started
                self._dirty = 0
        return new

    async def reinit(self, force=False):
        """
        [Trio] Refresh the full data and broadcast a full event when the
        data changed.

        - fetch_lock (double-checked with the freshness window of
          fetch_init) serializes concurrent refreshes;
        - identical data (old == new) does not broadcast;
        - without subscribers only the data is refreshed (no broadcast);
        - the full event is encoded and its delivery queued under the
          lock (it references data, which event threads may mutate as
          soon as the lock is released; the run_sync_soon queueing
          shares the FIFO of the inbox doorbells, so the full event is
          ordered against increments by the lock itself).

        Args:
            force (bool): Ignore the freshness window. RPC handlers that
                just modified the disk must pass force=True.
        """
        async with self._fetch_lock:
            new = await self.fetch_init(force)
            if new is None:
                return
            with self._lock:
                old = self.data
                if old == new:
                    return
                self.data = new
                if not self._subscribers:
                    return
                # Encode under the lock: the payload references data, and
                # data may be mutated in place as soon as the lock is
                # released. bytes are frozen.
                payload = ENCODER.encode(
                    ResponseEvent(t=self.TOPIC_NAME, o='full', v=self.data)
                )
                # Queue the delivery under the lock, exactly like the
                # doorbells of _ring: the run_sync_soon queue is the
                # delivery order, and the lock serializes every queueing
                # against the worker-thread on_event. A full event is
                # therefore always queued before any increment whose event
                # applied after its data snapshot -- never after (queueing
                # outside the lock would race the doorbells and could let
                # the full event trail a newer increment). Subscribers
                # that leave in between are skipped (delivery reads the
                # current set).
                try:
                    self._trio_token.run_sync_soon(self._deliver_all, payload)
                except trio.RunFinishedError:
                    pass

    # ---------------- event stream ----------------

    def on_event(self, event):
        """
        [任意线程] Event entry: apply under the lock and broadcast.

        - No actual change: nothing is broadcast;
        - no subscriber: the event is only applied (data stays fresh),
          nothing is scheduled;
        - _convert returns a single response or a list (multi-key
          events); everything is pushed inside one critical section.
        """
        with self._lock:
            if not self._apply(event):
                return
            # the event stream is alive and its data is up to date
            self._lastrun = time.monotonic()
            self._loaded = True
            self._running = True
            if not self._subscribers:
                return
            payload = self._convert(event)
            if type(payload) is list:
                # multi-key events: several responses pushed inside the
                # same critical section (the doorbell rings at most once)
                for p in payload:
                    self._push(p)
            else:
                self._push(payload)


class ResidentCache(EventSource):
    """
    Resident cache model (dimension B): runtime-produced data kept in
    memory forever.

    - business: log / preview / worker state / current running task are
      produced at runtime and events are the ONLY data source (no disk
      fallback -- losing an event loses the data forever). They must stay
      resident so a later front-end visit finds something to display;
      subscribing returns the in-memory data;
    - GC = False, TTL = None: never recycled by the data-expiry gc;
      memory is bounded by the inner structure of each source;
    - subscribe = in-memory snapshot + later incremental pushes.
    """


class DiskCache(EventSource):
    """
    Disk cache model (dimension B): content read from disk and cached so
    concurrent connections do not re-read the disk.

    - business: static content, NO push after subscription (no event
      stream, no RPC refresh): the full a subscriber received never
      expires. Content changes only come from subscription-condition
      changes (mod / lang / navigation) that rebuild the data through
      get_source -> reinit;
    - TTL (seconds, default 8 of the model, subclass may override):
      both the fetch freshness window and the recycle window of the
      data-expiry GC; a subclass sets TTL=None to disable both
      (never collected -- with GC=True and TTL=None the class stays out
      of _GC_CLASSES);
    - GC = True: recycle when the data TTL expired REGARDLESS of
      subscribers -- recycling a subscribed instance is harmless because
      there is no push channel after the full was sent (see the design
      doc, "DiskCache 订阅中回收安全"); a subclass may declare GC=False
      to stay resident, e.g. ConfigScanSource whose data is read
      lock-free by other modules (a rebuilt instance would read empty)
      and whose TTL only throttles re-reads;
    - subscribe = one full snapshot, then no communication.
    """
    GC = True
    # Default data freshness / recycle window of the cache model: most
    # DiskCache topics inherit it without declaring TTL.
    TTL = 8


class DiskCachePush(EventSource):
    """
    Disk cache + event push model (dimension B): caches topic data that
    can be rebuilt from disk AND pushes event-stream increments.

    - business: typical TaskQueue -- data = {pending, waiting} loaded from
      the disk schedule table, later changes flow in through worker
      TaskQueue events; a config-event linkage forces reinit refreshes
      and a successful refresh counts as data activity;
    - TTL (seconds, default 8 of the model, subclass may override):
      worker events / successful refreshes refresh _lastrun
      (keep-alive);
    - GC = True with GC_NEEDS_NO_SUBSCRIBER = True: recycle only when the
      TTL expired AND no subscriber is attached. A live subscriber keeps
      the instance: the push channel is bound to the instance and worker
      event gaps (a long running task) can exceed the TTL by far --
      recycling a subscribed instance would permanently cut the push (the
      next event would land on a fresh instance nobody is subscribed to);
    - subscribe = full + incremental pushes; events still arrive without
      subscribers and keep the instance alive / warm the cache for the
      next subscription.
    """
    GC = True
    GC_NEEDS_NO_SUBSCRIBER = True
    # Default data freshness / recycle window of the cache model: most
    # DiskCachePush topics inherit it without declaring TTL (TaskQueue
    # overrides with 5s).
    TTL = 8


class GlobalSource(BaseSource, metaclass=Singleton):
    """
    Registry shape (dimension A): globally unique instance.

    Instance management only -- no cache / push implementation. Pick a
    dimension-B model and inherit it, e.g.
    class WorkerSource(GlobalSource, ResidentCache).
    """

    @classmethod
    def _iter_idle_instances(cls):
        inst = cls.singleton_instance()
        return (inst,) if inst is not None else ()

    def _remove(self):
        type(self).singleton_remove_if(self)

    def _reconcile(self):
        # a concurrent data-expiry GC may have cleared the singleton
        # while get_source() -> subscribe() was in flight
        type(self).singleton_reinsert(self)


class ConfigSource(BaseSource, metaclass=SingletonNamed):
    """
    Registry shape (dimension A): instances keyed by config_name (the
    first constructor argument). Instance management only -- pick a
    dimension-B model and inherit it, e.g.
    class TaskQueueSource(ConfigSource, DiskCachePush).
    """

    def __init__(self, config_name):
        self.config_name = config_name
        super().__init__()

    @classmethod
    def _iter_idle_instances(cls):
        return [inst for _, inst in cls.singleton_items()]

    def _remove(self):
        type(self).singleton_remove_if(self.config_name, self)

    def _reconcile(self):
        type(self).singleton_reinsert(self.config_name, self)


class KeyedSource(BaseSource, metaclass=SingletonKeyed):
    """
    Registry shape (dimension A): instances keyed by the whole
    constructor argument tuple (metaclass SingletonKeyed). Subclasses
    keep natural constructor signatures such as
    __init__(self, mod_name, lang); each subclass owns its own registry
    (per-class metaclass storage). Instance management only -- pick a
    dimension-B model and inherit it, e.g.
    class ConfigNavSource(KeyedSource, DiskCache).
    """
    # The composite key of this instance. Assigned by the SingletonKeyed
    # metaclass when the instance is created (never set in __init__);
    # declared here so type checkers resolve the attribute.
    _singleton_key: tuple

    @classmethod
    def get(cls, *key):
        """
        [Trio] Get or create the instance of the composite key.

        The key is the whole positional argument tuple: cls(*key) calls
        the natural constructor signature. Registry lookup / creation and
        the _singleton_key bookkeeping happen in the SingletonKeyed
        metaclass.

        Returns:
            KeyedSource | None: None when the construction raised
                KeyError (e.g. the referenced structure is gone).
        """
        try:
            return cls(*key)
        except KeyError:
            return None

    @classmethod
    def _iter_idle_instances(cls):
        return [inst for _, inst in cls.singleton_items()]

    def _remove(self):
        type(self).singleton_remove_if(self._singleton_key, self)

    def _reconcile(self):
        type(self).singleton_reinsert(self._singleton_key, self)


class NoCachePush(BaseSource):
    """
    No-cache forwarding model (dimension B): nothing is cached in memory,
    the full view is built on subscribe and events are forwarded after
    that. Registry shape comes from dimension A (composed through
    inheritance) -- this class itself is registry-free and carries no
    config semantics: the event content protocol is NOT part of the
    model (_convert receives any external event, application layers such
    as GuiConfigSource decide what to accept).

    - subscribe() builds the full view (subclass hook _build_full, runs
      in a thread) and returns the encoded full payload. Concurrent
      subscribers of the same instance -- same key -- share ONE build
      single-flight: while a build runs, later subscribers wait and reuse
      its payload (same key -> same view; the stale window equals the
      private-build window). The payload expires when the last waiter
      took it, so later subscribers always rebuild (freshness is never
      cached);
    - on_event() forwards events filtered / converted by the subclass
      (_convert), unrelated ones are dropped;
    - reinit() rebuilds the full view and broadcasts it to the current
      subscribers (RPC-driven full refresh, e.g. DevAssets); without
      subscribers it is a no-op (nothing cached, nothing to refresh).

    Lifecycle: GC = False -- nothing to expire, never in the data-expiry
    gc loop. The instance removes itself from its registry when the LAST
    subscriber leaves (unsubscribe): nothing is cached, so a departed
    viewer leaves no value behind; the next get() rebuilds it.
    """
    # Sentinel: no reusable build payload
    _NO_PAYLOAD = object()
    # Sentinel: the build failed. Waiters translate it to None (registered,
    # no full); subscribers arriving after the failure must rebuild, never
    # reuse it as an empty-view result.
    _FAILED = object()

    def __init__(self):
        super().__init__()
        # Single-flight full build (Trio thread only): plain flags + one
        # event, no lock needed.
        self._building = False
        self._build_event = None  # completion signal of the running build
        self._build_payload = self._NO_PAYLOAD  # bytes | None | sentinel
        self._build_waiters = 0

    # ---------------- subscribe: single-flight full build ----------------

    async def subscribe(self, sub):
        """
        [Trio] Register and return the encoded full payload.

        The build happens BEFORE registration: the returned payload must
        be sent without any await in between, so the full event precedes
        every later increment (events falling into the build window are
        dropped, same as the private-build window of the previous design).
        A falsy view returns None: the subscriber is registered but no
        full is sent (empty-view semantics, same as empty data of cache
        sources). After registration the instance reconciles with its
        registry (dimension A hook, see BaseSource._reconcile): when a
        concurrent GC removed it while the get_source() -> subscribe()
        flow was in flight, it re-registers itself.
        """
        payload = await self._get_payload()
        with self._lock:
            if self._trio_token is None:
                self._trio_token = trio.lowlevel.current_trio_token()
            self._subscribers.add(sub)
        self._reconcile()
        return payload

    def unsubscribe(self, sub):
        """
        [Trio] Unsubscribe. Idempotent.

        When the last subscriber leaves, the instance is removed from its
        registry: nothing is cached, the next subscription rebuilds it
        (dimension A _remove, identity-checked).
        """
        with self._lock:
            self._subscribers.discard(sub)
            empty = not self._subscribers
        if empty:
            self._remove()

    async def _get_payload(self):
        """
        [Trio] Single-flight full build shared by concurrent subscribers.

        While a build is running, subscribers wait for it and reuse its
        payload (same key -> same view). The payload is published only to
        the waiters of that build and expires when the last one took it:
        a later subscriber always rebuilds, so the full view is never
        stale by more than one build window. On build failure the waiters
        receive None (registered, no full) and the builder re-raises;
        subscribers arriving after the failure rebuild (the failure
        sentinel is never reused as a result).
        """
        if self._building:
            # a concurrent build is running: wait and reuse its payload
            self._build_waiters += 1
            try:
                event = self._build_event
                await event.wait()
                payload = self._build_payload
                if payload is self._FAILED:
                    # the build failed: register without a full (same
                    # semantics as the failing builder's own path)
                    return None
                # the builder published bytes | None before setting the
                # event: never the sentinel here
                return payload
            finally:
                self._build_waiters -= 1
                if self._build_waiters == 0:
                    # last waiter took the payload: expire it
                    self._build_payload = self._NO_PAYLOAD
        payload = self._build_payload
        if payload is not self._NO_PAYLOAD and payload is not self._FAILED:
            # a build just finished and its last waiter is not awake yet:
            # reuse it (fresh within one scheduling window); a failed
            # build leaves the failure sentinel, which is never reused --
            # later subscribers rebuild
            return payload
        # no build running: build ourselves and publish to the waiters
        self._building = True
        event = trio.Event()
        self._build_event = event  # fresh event per build: stale signals never wake new waiters
        try:
            view = await self._build_full()
            payload = (
                ENCODER.encode(ResponseEvent(t=self.TOPIC_NAME, o='full', v=view))
                if view else None
            )
            if self._build_waiters:
                self._build_payload = payload
                event.set()
            else:
                # no waiter to take it: leave no stale result behind
                # (a leftover failure sentinel must not survive a
                # successful rebuild)
                self._build_payload = self._NO_PAYLOAD
            return payload
        except BaseException:
            # wake the waiters even on failure: they must not hang forever.
            # Publish the failure sentinel (not None): waiters translate it
            # to None, and subscribers arriving after the failure rebuild
            # instead of reusing it as an empty-view result.
            if self._build_waiters:
                self._build_payload = self._FAILED
                event.set()
            raise
        finally:
            self._building = False

    async def _build_full(self):
        """
        [Trio, 锁外] Build the full view. Subclass hook, runs inside the
        single-flight path of subscribe (one build per key at a time).
        Return the view data; falsy means an empty view (subscriber is
        registered, no full is sent).
        """
        raise NotImplementedError

    # ---------------- RPC-driven full refresh ----------------

    async def reinit(self, force=False):
        """
        [Trio] Rebuild the full view and broadcast it to every current
        subscriber. No-op without subscribers (nothing cached, nothing to
        refresh). Used by sources refreshed through RPC (e.g. DevAssets
        after a resource operation).

        The payload is queued under the lock through the run_sync_soon
        queue (same FIFO as the inbox doorbells), so a full event is
        ordered against the forwarding increments by the lock itself.
        """
        with self._lock:
            if not self._subscribers:
                return
        view = await self._build_full()
        if not view:
            # empty view: nothing to broadcast
            return
        payload = ENCODER.encode(ResponseEvent(t=self.TOPIC_NAME, o='full', v=view))
        with self._lock:
            try:
                self._trio_token.run_sync_soon(self._deliver_all, payload)
            except trio.RunFinishedError:
                pass

    # ---------------- on_event forwarding ----------------

    def _convert(self, event):
        """
        [锁内] One event -> a response, or None when the event is not
        displayed by this view (dropped). Subclass hook.

        Default: no forwarding (every event dropped) -- a view source
        without increments (static / one-shot view) is legal; override to
        filter / convert the events of the view.
        """
        return None

    def on_event(self, event):
        """
        [任意线程] Locked: filter / convert by the subclass, broadcast the
        responses. A list payload (RPC responses) is expanded into single
        events inside the lock.
        """
        with self._lock:
            if not self._subscribers:
                # race window of the registry: no subscriber any more, drop
                return
            events = event if isinstance(event, list) else [event]
            was_empty = not self._inbox
            for e in events:
                resp = self._convert(e)
                if resp is not None:
                    self._inbox.append(resp)
            if was_empty and self._inbox:
                self._ring()
