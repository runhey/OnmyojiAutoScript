from collections import deque
from typing import TYPE_CHECKING

import anyio
from msgspec import DecodeError, ValidationError

from oas.backend.mpipe.token_backend import token_table
from oas.backend.reactive.base_topic import BaseTopic as BaseMixin
from oas.backend.reactive.event import (
    AccessDenied,
    LocalFlutterOnlyError,
    ResponseEvent,
    RpcValueError,
)
from oas.backend.reactive.rx_trio import AsyncReactiveCallback, async_reactive_nocache
from oas.ext.singleton import SingletonNamed
from oas.logger import logger

if TYPE_CHECKING:
    # For IDE typehint, avoid recursive import
    from oas.backend.ws.ws_server import WebsocketTopicServer


class BaseTopic(AsyncReactiveCallback, BaseMixin, metaclass=SingletonNamed):
    # Topic-level local restriction: when True, subscribing to this
    # topic and every rpc under it requires a valid local token on the
    # connection (verified at operation time, never cached). Default
    # topics are public; mark the sensitive ones explicitly.
    REQUIRE_LOCAL_FLUTTER = False
    # Per-subscription send backlog (encoded payloads) for slow
    # connections. The deque maxlen bounds the backlog; on overflow the
    # oldest payload is silently dropped (client-side slowness is not
    # logged on the backend, see deliver).
    OUTBOX_MAXLEN = 128

    def __init__(self, conn_id, server: 'WebsocketTopicServer'):
        """
        Create a data topic, that supports subscribe/unsubscribe
        and sends data changes once subscribed

        Args:
            conn_id (str):
        """
        self.conn_id = conn_id
        self.server = server
        # Current subscribed source instance; None when not subscribed.
        # Resubscription state (loop thread only; plain flags, no lock):
        self._src = None
        self._busy = False  # a resubscribe round (incl. the catch-up loop) is running
        self._dirty = (
            False  # a trigger arrived while busy -> catch up with the newest state
        )
        self._closed = False  # op_unsub executed -> the running round must abort
        # True while the client of this connection may hold data of this
        # topic (a full snapshot or an increment was delivered / sent and
        # no clear followed): a rebind that yields no snapshot must then
        # state the empty data explicitly (see _clear_client_data) -- the
        # client would otherwise keep the previous source's data forever,
        # because subscribe stays silent on empty data and a cache source
        # pushes no increments that could ever correct it.
        self._client_has_data = False
        # Reliable send backlog of the current source (see deliver). All
        # fields are only touched on the loop thread. The deque maxlen
        # bounds the backlog: appending to a full outbox silently drops
        # the oldest payload, so a permanently stuck connection can never
        # grow memory without bound (losing messages is preferred to
        # running out of memory).
        self._outbox: 'deque[bytes]' = deque(maxlen=self.OUTBOX_MAXLEN)
        self._sending = False  # the single-flight outbox drain task is running
        self._send_scope = None  # cancel scope of the running drain task
        # Task group of the connection, read on op_sub: outbox drain tasks
        # spawned from deliver() die with the connection. AnyIO has no
        # "parent task group" query, the server hands its connection task
        # group over explicitly (see op_sub).
        self._task_group = None

    def __str__(self):
        return f'{self.TOPIC_NAME}({self.conn_id})>'

    def _check_local_flutter(self):
        """
        Verify the connection's local token in real time.

        Raises:
            LocalFlutterOnlyError: When the connection has no valid token
        """
        if not token_table.verify(self.server.local_token):
            raise LocalFlutterOnlyError('local token required')

    def deliver(self, payload):
        """
        [loop 线程，同步] Deliver one encoded payload to this topic.

        Called by the source of this topic for every increment (the
        source broadcasts from _sync_to_loop / AnyIO.call_soon on the
        loop thread, so this method is synchronous and never awaits).

        - Fast path: send_nowait into the connection's send buffer;
        - on WouldBlock (send buffer full, slow connection) the payload
          goes to the outbox and a single-flight drain task is spawned;
          the task sends with await send(), so it suspends on the
          channel's backpressure and resumes automatically when the send
          buffer frees a slot -- no polling and no wake-up of the
          connection's task_send is needed;
        - while a drain task is running every new payload is appended to
          the outbox (never sent directly): one sender owns the FIFO, so
          a backlogged message can never be overtaken by a newer one;
        - the outbox is bounded (OUTBOX_MAXLEN, deque maxlen): on
          overflow the oldest payload is silently dropped -- a slow
          client loses messages instead of the backend running out of
          memory (client-side problem, not logged on the backend).

        Ordering contract: the full event is sent by _resubscribe right
        after registration, before any increment reaches this method, and
        the outbox is dropped whenever the topic unbinds its source
        (_drop_outbox), so a full event is never followed by stale
        increments of a previous source.

        The delivery marks the client as holding data: an increment may be
        the first payload a client receives (the initial snapshot was
        empty and subscribe stayed silent), and a later rebind that yields
        no snapshot must clear it (see _clear_client_data).

        Note: this runs as a plain loop callback when a source rings the
        doorbell, so it may only use what works without an async task
        context -- send_nowait does, task_group.start_soon does not (see
        AnyIO.call_soon).
        """
        self._client_has_data = True
        if self._sending:
            # A drain task is running (it may be suspended on a full send
            # buffer while the outbox is empty): always queue, never
            # send_nowait, which could overtake the message the task is
            # currently sending.
            self._outbox.append(payload)
            return
        try:
            self.server.send_nowait(payload)
        except anyio.WouldBlock:
            # Send buffer full: queue the payload and drain it through a
            # send task that waits for free slots.
            self._outbox.append(payload)
            self._start_outbox_send()

    def _start_outbox_send(self):
        """
        [loop 线程，同步] Spawn the single-flight outbox drain task.

        Only called when no drain task is running (_sending is False) and
        the outbox is non-empty. The task group is read on op_sub (the
        topic is created inside the connection's task_job, which runs in
        the connection task group): the task dies with the connection.
        """
        task_group = self._task_group
        if task_group is None:
            # Out of the connection context (direct instantiation in
            # tests / misuse): the backlog stays queued, nothing can send
            # it. Unreachable in the ws server (op_sub always runs inside
            # a connection task group).
            logger.error(f'{self} cannot spawn outbox send task (no task group)')
            return
        self._sending = True
        task_group.start_soon(self._outbox_send)

    async def _outbox_send(self):
        """
        [anyio 任务] Drain the outbox with backpressure, then self-terminate.

        One task per backlog episode: it sends one payload per free slot
        of the connection's send buffer. When the buffer is full the task
        suspends on await send and the event loop resumes it when a slot
        frees up (automatic refill, no new events required). Exits when
        the outbox is empty; the next WouldBlock starts a fresh task.

        The cancel scope lets op_unsub / source rebinding stop the task.
        Cancellation is best-effort: a task already suspended on a full
        send buffer can only be woken by the channel itself (a slot freed
        by task_send, or the channel closing with the connection), so a
        popped payload may still go out if the send completes before the
        cancellation takes effect. That message always precedes the full
        event of the next source (the resubscribe round sends it after
        dropping the backlog), so the client stays eventually consistent
        (full events replace the whole view).
        """
        cancelled_class = anyio.get_cancelled_exc_class()
        try:
            with anyio.CancelScope() as scope:
                self._send_scope = scope
                while self._outbox:
                    payload = self._outbox.popleft()
                    if not await self.server.send(payload):
                        # send buffer closed: the remaining backlog dies
                        # with the connection
                        break
        except cancelled_class:
            # Canceled by op_unsub / source rebinding (best-effort, see
            # above): swallow the exception so the task ends normally --
            # an unhandled cancellation would surface as a task group
            # error on the still-alive connection.
            pass
        except Exception:
            # Unexpected send failure: log it. The rest of the backlog
            # self-heals on the next episode (a fresh drain task sends
            # what is left).
            logger.exception(f'{self} outbox send failed')
        finally:
            # Also runs on cancellation: the task must never leave
            # _sending stuck at True.
            self._sending = False
            self._send_scope = None

    def _drop_outbox(self):
        """
        [loop 线程，同步] Drop the outbox backlog and cancel its drain task.

        Called when the topic leaves its source (op_unsub) or rebinds to
        a new one (_resubscribe): backlogged payloads belong to the old
        source and must never be emitted after the full event of the new
        source. The cancel is best-effort (see _outbox_send): a payload
        already submitted to the send buffer may still go out, but always
        before the new full event.
        """
        self._outbox.clear()
        scope = self._send_scope
        if scope is not None:
            scope.cancel()

    @async_reactive_nocache
    async def _resubscribe(self):
        """
        Side-effect carrier of the source-model subscription: unsubscribe
        the old source, resolve the new subscription (get_source), register
        the new source and send the full event. When the new state yields
        no snapshot (no source / empty source), the client's view of the
        old source is cleared instead (see _clear_client_data): subscribe
        stays silent on empty data, so nothing else would ever replace the
        previous source's data on screen.

        Latest-wins merging (see doc/2026-09-03_topic-source-subscribe-v2.md):

        - at most ONE round runs per topic instance (entry gate `_busy`);
        - triggers arriving while a round runs (rapid navigation changes,
          dependency broadcasts) only set `_dirty` and return: they never
          start a second round, so the expensive full builds of the
          intermediate states are skipped;
        - when the running round finishes it drops its own result if
          `_dirty` is set (it is stale by then) and catches up with one
          more round reading the newest state; the loop ends when a round
          completes without new triggers (the last state is sent);
        - `op_unsub` sets `_closed`: the running round aborts at its next
          checkpoint, unregisters itself and never re-registers.

        The old `_gen` generation counter was removed: this instance only
        runs one round at a time, so no round can ever be "outdated" by a
        concurrent one. Serialization of full builds across connections
        sharing one source instance is the source's own job
        (NoCachePush single-flight).
        """
        if self._busy:
            # a round is running: merge this trigger into it
            self._dirty = True
            return
        self._busy = True
        try:
            while not self._closed:
                self._dirty = False
                old = self._src
                if old is not None:
                    old.unsubscribe(self)
                    self._src = None
                    # The outbox holds increments of the old source:
                    # drop them (and the drain task) so they can never be
                    # emitted after the full event of the new source.
                    self._drop_outbox()
                source = await self.get_source()
                if self._closed:
                    # unsubscribed while resolving: abort without registering
                    break
                if self._dirty:
                    # a newer trigger arrived while resolving: skip this
                    # round (no build) and catch up with the newest state
                    continue
                if source is None:
                    # no source right now: the topic has no data to show. A
                    # client that still holds the previous source's view
                    # must be told (see _clear_client_data); the next
                    # dependency change re-runs this flow either way
                    await self._clear_client_data()
                    break
                self._src = source
                snapshot = await source.subscribe(self)
                if self._closed:
                    # op_unsub ran while the build was in flight: undo the
                    # registration and abort
                    source.unsubscribe(self)
                    self._src = None
                    break
                if self._dirty:
                    # stale result: drop it (the next round unregisters)
                    # and catch up with the newest state
                    continue
                if snapshot is None:
                    # the new source's snapshot is empty: subscribe stays
                    # silent on empty data, so the client view of the
                    # previous source must be cleared explicitly
                    await self._clear_client_data()
                else:
                    self._client_has_data = True
                    # Ordering contract: right after registration, without
                    # any await, send the full event so it precedes every
                    # later increment.
                    try:
                        self.server.send_nowait(snapshot)
                    except anyio.WouldBlock:
                        # rare fallback; increments may sneak in during the
                        # await, which is an acceptable window (slow
                        # connection, dropped by heartbeat)
                        await self.server.send(snapshot)
                if self._dirty:
                    # a trigger arrived while sending: catch up once more
                    continue
                break
        finally:
            self._busy = False

    async def _clear_client_data(self):
        """
        [loop] Drop the client's view of this topic (a `del` at the data
        root: the client forgets the topic data, the state before its
        first full).

        Needed when a rebind yields no snapshot (no source right now, or
        an empty one): a client that already holds the previous source's
        data would otherwise display it forever, because subscribe stays
        silent on empty data and nothing pushes a correction (a cache
        source has no increments at all). A fresh subscription sends
        nothing: no client holds a view to replace.

        The event is ordered like the full event of a rebind (sent with
        send_nowait right after the round resolved, increments of the new
        source follow it), so a clear is never seen after newer data.
        """
        if not self._client_has_data:
            # the client holds nothing: nothing to replace
            return
        self._client_has_data = False
        event = ResponseEvent(t=self.TOPIC_NAME, o='del')
        try:
            self.server.send_nowait(event)
        except anyio.WouldBlock:
            # rare fallback, same window as the full event of a rebind
            # (slow connection, dropped by heartbeat)
            await self.server.send(event)

    async def op_sub(self):
        """
        Subscribe to this topic, once subscribe the data will flow

        When receiving a "sub" event from client, the data flows
        --> Topic.get_source()
            the topic is bound to its source, the source snapshot is sent
            (subscribe() returns the encoded snapshot, sent immediately)

        Changes may come from:
        - backend background task that updates data
        - external database changes
        - another topic changes the dependency ot current topic
        - another client changes the data of current topic

        When a reactive dependency (ConnState) changes, the data flows:
        --> DataSource.data.mutate(self, data)
        --> @async_reactive_nocache
            changes will broadcast to callback function
            --> _resubscribe (unsubscribe the old source, resolve get_source
                again, bind the new source, send a new full)
        """
        if self._task_group is None:
            # op_sub runs inside the connection's task_job, and the server
            # hands the task group of that connection over explicitly
            # (AnyIO has no parent task group query): outbox drain tasks
            # spawned later by deliver() die with the connection.
            self._task_group = self.server.conn_task_group
        await self._resubscribe

    async def get_source(self):
        """
        Resolve the source this topic should bind to.

        Returns:
            BaseSource | None:
                - the source instance to register; the initial full event
                  comes from source.subscribe() (cache sources snapshot
                  their data, viewport sources build their view);
                - None: no source right now, subscribe silently.

        Data preparation: topics that need fresh full data (ConfigScan /
        TaskQueue / one-shot sources / DevAssets) must `await
        source.reinit()` before returning. Sources without a full data
        source have an empty reinit, calling it costs nothing.

        May await ConnState etc. reactive dependencies; they form the
        observation chain that re-runs _resubscribe on changes, so a
        dependency change automatically re-binds the topic to the source
        resolved by the new conditions.
        """
        return None

    async def op_unsub(self):
        """
        Release current data topic
        """
        # Abort any running _resubscribe round: it checks `_closed` at its
        # next checkpoint, unregisters itself and never re-registers after
        # the connection is gone (no leak into resident sources).
        self._closed = True
        # Drop the outbox backlog and cancel its drain task: stale
        # increments die with the subscription, a canceled await send
        # never emits its popped payload.
        self._drop_outbox()
        src = self._src
        if src is not None:
            src.unsubscribe(self)
            self._src = None
        cls = self.__class__
        cls.singleton_remove(self.conn_id)

    async def op_rpc(self, func, value, rpc_id):
        """
        Do RPC call on current topic

        Args:
            func (str): RPC method name
            value (Any): RPC method args
            rpc_id (str):
        """
        try:
            method = self.rpc_methods[func]
        except KeyError:
            msg = f'RPC method not found "{func}"'
            event = ResponseEvent(t=self.TOPIC_NAME, v=msg, i=rpc_id)
            await self.server.send(event)
            return

        # local check must happen BEFORE the call executes (never
        # inside the method body): a rejected request never ran, so a
        # renewal retry is a first execution, not a re-execution
        # (idempotency). Inside the try so the existing except branch
        # returns the error response carrying the rpc_id.
        try:
            if method.require_local_flutter or self.REQUIRE_LOCAL_FLUTTER:
                self._check_local_flutter()
            await method.call_async(self, value)
        except (
            ValidationError,
            DecodeError,
            UnicodeDecodeError,
            AccessDenied,
            RpcValueError,
        ) as e:
            # input errors
            msg = f'{e.__class__.__name__}: {e}'
            event = ResponseEvent(t=self.TOPIC_NAME, v=msg, i=rpc_id)
            await self.server.send(event)
            return
        except Exception as e:
            # unexpected internal errors
            logger.exception(e)
            msg = f'{e.__class__.__name__}: {e}'
            event = ResponseEvent(t=self.TOPIC_NAME, v=msg, i=rpc_id)
            await self.server.send(event)
            return

        # success
        # RPC success has no return value sent, omitting "v" means success, having "v" means error
        # The real RPC response will go through existing topic subscription
        event = ResponseEvent(t=self.TOPIC_NAME, i=rpc_id)
        await self.server.send(event)
        return
