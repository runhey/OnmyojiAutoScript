from collections import deque
from typing import Deque, Optional, Type, Union

import anyio
import msgspec
from anyio import Event
from anyio.abc import ObjectReceiveStream, ObjectSendStream, TaskGroup
from msgspec import DecodeError, EncodeError, ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from oas.backend.mpipe.token_backend import read_token_header, token_table
from oas.backend.reactive.event import (
    AccessDenied,
    ElectronOnlyError,
    RequestEvent,
    ResponseEvent,
)
from oas.backend.reactive.safeid import SafeIDGenerator
from oas.backend.ws.ws_topic import BaseTopic
from oas.logger import logger

CHANNEL_ERRORS = (
    anyio.BrokenResourceError,
    anyio.BusyResourceError,
    anyio.ClosedResourceError,
    anyio.EndOfStream,
)
WEBSOCKET_ERRORS = (WebSocketDisconnect, RuntimeError)
DECODE_ERRORS = (ValidationError, DecodeError, UnicodeDecodeError)
ENCODE_ERRORS = (EncodeError, UnicodeEncodeError)
REQUEST_EVENT_DECODER = msgspec.json.Decoder(RequestEvent)
RESPONSE_EVENT_ENCODER = msgspec.json.Encoder()
CONN_ID_GENERATOR = SafeIDGenerator(prefix='conn')


class WebsocketTopicServer:
    """ """

    """
    Class methods that manage all connections
    """

    # active connections registry: key = connection id, value = server.
    # Registered in serve() after accept, unregistered on exit. Used by
    # the rotation notification (Phase 5) to reach restricted-subscription
    # connections.
    active: 'dict[str, WebsocketTopicServer]' = {}

    # Set by close_all_connections() on server shutdown; every connection
    # watches it and closes with 1001. The lifespan re-arms it with a fresh
    # Event on startup: this class attribute outlives a single app run, and
    # a still-set event would close every later connection immediately.
    server_terminated = Event()

    @classmethod
    async def endpoint(cls, ws: WebSocket):
        """
        Websocket endpoint
        """
        server = cls(ws)

        try:
            await server.serve()
        finally:
            await server.cleanup()

    @classmethod
    async def close_all_connections(cls):
        """
        Iterates over all active connections and requests them to close gracefully.
        """
        WebsocketTopicServer.server_terminated.set()

    # messages in send_buffer will be sent first, then lossy_buffer
    # if websocket is busy, send_buffer will create back-pressure, old messages in lossy buffer will be dropped
    SEND_BUFFER_LENGTH = 32
    LOSSY_BUFFER_LENGTH = 128
    # If no activity for X seconds,
    # we will send a "ping" to client
    PING_INTERVAL = 30
    # When client received a "ping", client should respond with a "pong" within X seconds,
    # otherwise we will close the connection
    PONG_TIMEOUT = 15
    # all topic classes, subclasses should override this
    # key: topic name, value: topic class
    ALL_TOPIC_CLASS: 'dict[str, Type[BaseTopic]]' = {}
    # default subscribed topics on connection init
    # key: topic name, value: topic class
    DEFAULT_TOPIC_CLASS: 'dict[str, Type[BaseTopic]]' = {}

    """
    Instance methods that manage current connection
    """

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.id = CONN_ID_GENERATOR.get()
        # electron token from the handshake header X-Alasio-Token; '' when
        # absent. Kept per-connection, updated by a successful renewal
        # (o='auth'). Verified in real time for restricted operations.
        self.auth_token = ''

        self.conn_terminated = Event()
        # timestamp of last activity, used to calculate the next "ping"
        self.last_active = 0.0
        # track if "pong" is received
        self.pong_received = Event()
        # buffer the message to be sent
        self.send_buffer: 'ObjectSendStream[bytes]' = None
        self.lossy_buffer = deque(maxlen=self.LOSSY_BUFFER_LENGTH)
        self.send_event = Event()
        # All subscribed topics
        # key: topic name, value: topic object Topic(self.id)
        self.subscribed: 'dict[str, BaseTopic]' = {}
        # Task group of this connection, set by serve() while the connection
        # lives: a topic reads it on op_sub and spawns its outbox drain tasks
        # on it, so they die with the connection. AnyIO has no "parent task
        # group" query (Trio: current_task().parent_nursery), so the group is
        # handed over explicitly.
        self.conn_task_group: 'Optional[TaskGroup]' = None

    def __str__(self):
        return f'WebsocketServer({self.id})'

    """
    Websocket lifespan
    """

    async def cleanup(self):
        """
        Cleanup all subscribed topics
        """
        # cache current subscribed and clear, to make cleanup atomic
        topics = list(self.subscribed.values())
        self.subscribed = {}
        for topic in topics:
            try:
                await topic.op_unsub()
            except Exception as e:
                logger.exception(e)
                continue

    async def serve(self):
        """
        Serve a websocket connection, start tasks for receive, send, heartbeat
        """
        try:
            await self.ws.accept()
            # accept success, update activity
            self.last_active = anyio.current_time()
        except WEBSOCKET_ERRORS:
            await self.close()
            return

        # Login layer: validate after accept. A refused handshake would
        # only surface as 1006 to the browser and the frontend could not
        # read the close code; accept-then-close delivers the real 4001.
        # A valid electron token passes without JWT (Electron exemption,
        # aligned with the http /api/auth/renew exemption).
        #
        # The reason is a stable, machine-readable token (not prose): the
        # frontend leaves for the login page exactly when it reads it, and
        # treats every other refused handshake (the backend restarting, an
        # old process shutting down, an admission rule) as a refusal of that
        # one connection instead of an ended session. Keep it in sync with
        # the frontend ws client and with tests/ws_fixtures/messages.json
        # (asserted on both sides).
        if not await self._check_login():
            await self.close(4001, 'alasio:auth-failed')
            return

        # Read the electron token from the handshake headers (ws.headers
        # keeps the handshake headers after accept).
        self.auth_token = read_token_header(self.ws)

        # register into the active connections registry
        WebsocketTopicServer.active[self.id] = self
        try:
            # handle messages
            async with anyio.create_task_group() as task_group:
                # topics read the connection task group on op_sub: outbox
                # drain tasks spawned by deliver() die with the connection
                self.conn_task_group = task_group
                # init before handing messages
                await self.init()

                # open 2 buffers, send buffer and recv buffer
                # start 4 async tasks, sender, receiver, job handler, heartbeat handler

                # send buffer, set send buffer first
                self.send_buffer, recv = anyio.create_memory_object_stream(
                    self.SEND_BUFFER_LENGTH
                )
                task_group.start_soon(self.task_send, recv, self.lossy_buffer)

                # recv buffer
                send, recv = anyio.create_memory_object_stream(8)
                task_group.start_soon(self.task_recv, send)
                task_group.start_soon(self.task_job, recv)

                # heartbeat
                task_group.start_soon(self.task_heartbeat)
        finally:
            # the connection task group is closed: a topic that outlived it
            # logs instead of trying to start a task on a dead group
            self.conn_task_group = None
            # unregister from the active connections registry
            try:
                WebsocketTopicServer.active.pop(self.id, None)
            except Exception:
                pass

    async def _check_login(self):
        """
        Validate the login layer on the handshake: a valid electron token
        passes without JWT (only the local Electron network layer can
        supply a table token), otherwise the alasio_token cookie JWT must
        be valid.

        Returns:
            bool: True when the connection is logged in
        """
        if token_table.verify_header(self.ws):
            return True
        try:
            import jwt as pyjwt

            from oas.backend.auth.auth import JWT_MANAGER
        except ImportError:
            # oas.backend.auth is not migrated yet (and PyJWT is not a
            # dependency of this backend yet either): only the electron
            # token can be validated, every other handshake is refused --
            # the same answer Alasio gives for an invalid cookie JWT.
            return False
        token = self.ws.cookies.get('alasio_token', '')
        try:
            JWT_MANAGER.validate_token(token)
        except pyjwt.PyJWTError:
            return False
        return True

    async def init(self):
        """
        Initialization after websocket established
        """
        # Default subscribe
        for topic_name, topic_class in self.DEFAULT_TOPIC_CLASS.items():
            topic = topic_class(self.id, self)
            self.subscribed[topic_name] = topic

    async def close(self, code=1000, reason=None):
        """
        Close websocket connection with error handling

        Args:
            code (int):
            reason (str | None):
        """
        if self.ws.application_state != WebSocketState.DISCONNECTED:
            try:
                await self.ws.close(code=code, reason=reason)
            except WEBSOCKET_ERRORS:
                pass

    """
    Websocket methods
    """

    @staticmethod
    def _encode_msg(
        data: 'Union[ResponseEvent, list[ResponseEvent], bytes]',
    ) -> 'Optional[bytes]':
        # return directly if already bytes
        if isinstance(data, bytes):
            return data
        # encode message
        try:
            return RESPONSE_EVENT_ENCODER.encode(data)
        except ENCODE_ERRORS as e:
            # invalid data, this shouldn't happen
            logger.error(f'Failed to encode data {data}')
            logger.exception(e)
            return None
        except Exception as e:
            # this shouldn't happen
            logger.error(f'Failed to encode data {data}')
            logger.exception(e)
            return None

    def _set_send_event(self):
        # safely clear anyio.Event()
        event = self.send_event
        self.send_event = Event()
        event.set()

    async def send(self, data: 'Union[ResponseEvent, list[ResponseEvent], bytes]'):
        """
        Send an event to send buffer

        Returns:
            bool: If success
        """
        data = self._encode_msg(data)
        if data is None:
            return False
        try:
            await self.send_buffer.send(data)
        except CHANNEL_ERRORS:
            # buffer closed
            return False
        self._set_send_event()
        return True

    def send_nowait(self, data: 'Union[ResponseEvent, list[ResponseEvent], bytes]'):
        """
        Send an event to send buffer without blocking

        Returns:
            bool: If success

        Raises:
            anyio.WouldBlock:
        """
        data = self._encode_msg(data)
        if data is None:
            return False
        try:
            self.send_buffer.send_nowait(data)
        except CHANNEL_ERRORS:
            # buffer closed
            return False
        self._set_send_event()
        return True

    def send_lossy(self, data: 'Union[ResponseEvent, list[ResponseEvent], bytes]'):
        """
        Send an event to lossy buffer

        Returns:
            bool: If success
        """
        data = self._encode_msg(data)
        if data is None:
            return False
        self.lossy_buffer.append(data)
        self._set_send_event()
        return True

    async def send_error(self, data: 'Union[ResponseEvent, Exception, str, bytes]'):
        """
        Send data as error
        """
        # convert errors
        if isinstance(data, Exception):
            data = f'{data.__class__.__name__}: {data}'
        # convert to event
        if isinstance(data, str):
            data = ResponseEvent(t='error', o='full', v=data)
        data = self._encode_msg(data)
        if data is None:
            return False
        await self.send(data)

    """
    Async tasks
    """

    async def _ws_receive(self, ws: WebSocket):
        """
        Similar to WebSocket.receive_bytes but accept both text and bytes and return bytes

        Returns:
            bytes | str:

        Raises:
            WebSocketDisconnect:
            RuntimeError:
            ValidationError:
        """
        if ws.application_state != WebSocketState.CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await ws.receive()
        ws._raise_on_disconnect(message)

        # receive success, update activity
        self.last_active = anyio.current_time()

        try:
            data = message['bytes']
            if data is not None:
                return data
        except KeyError:
            pass
        try:
            data = message['text']
            if data is not None:
                return data
        except KeyError:
            # This shouldn't happen
            pass

        # We re-raise as ValidationError to ignore this message
        raise ValidationError(
            'Websocket event does not contain bytes nor text'
        ) from None

    async def task_recv(self, send_buffer: 'ObjectSendStream[RequestEvent]'):
        """
        Coroutine task that receive from websocket and send to send_buffer
        """
        while True:
            try:
                message = await self._ws_receive(self.ws)
            except WEBSOCKET_ERRORS:
                # websocket disconnected
                # we capture and exit silently, so anyio will wait other task to finish current job
                break
            except DECODE_ERRORS as e:
                # invalid message, we ignore this and hope the next message is good
                await self.send_error(e)
                continue

            # heartbeat message
            if message == b'pong' or message == 'pong':
                self.pong_received.set()
                continue

            # normal message
            try:
                data = REQUEST_EVENT_DECODER.decode(message)
            except DECODE_ERRORS as e:
                # parse error is acceptable, just drop to message
                await self.send_error(e)
                continue
            except Exception as e:
                logger.error(f'Failed to decode message {message}')
                logger.exception(e)
                continue
            try:
                await send_buffer.send(data)
            except CHANNEL_ERRORS:
                # channel closed, skip sending
                continue

        # close from upstream to downstream, so downstream can still finish current job
        await send_buffer.aclose()
        # logger.info(f'{self} task_recv closed')

    async def task_job(self, recv_buffer: 'ObjectReceiveStream[RequestEvent]'):
        """
        Coroutine task that receive data from recv_buffer and do the actual job
        """
        while True:
            try:
                event = await recv_buffer.receive()
            except CHANNEL_ERRORS:
                # websocket closed -> recv_buffer closed
                break

            # do jobs,
            # jobs will send data to send_buffer
            try:
                await self.handle_job(event)
            except AccessDenied as e:
                await self.send_error(e)
                continue
            except Exception as e:
                logger.exception(e)
                await self.send_error('Internal Error')
                continue

        # close from upstream to downstream, so downstream can still finish current job
        if self.send_buffer is not None:
            await self.send_buffer.aclose()
            # notify task_send to close
            self._set_send_event()
        # task_job is the final downstream, once it finished, we tell task_heartbeat to close
        self.conn_terminated.set()
        # logger.info(f'{self} task_job closed')

    async def task_send(
        self,
        send_buffer: 'ObjectReceiveStream[bytes]',
        lossy_buffer: 'Deque[bytes]',
    ):
        """
        Coroutine task that receive data from send_buffer and send to websocket
        """
        while True:
            # Priority 1: receive from send_buffer. An empty stream reports
            # which side is gone: EndOfStream when every sender closed it
            # (task_job / task_recv on the way out), ClosedResourceError or
            # BrokenResourceError once the buffer itself is closed, WouldBlock
            # while it is merely empty for now (Trio: _state / _closed were
            # read directly, AnyIO keeps them private).
            data = None
            try:
                data = send_buffer.receive_nowait()
            except anyio.WouldBlock:
                # empty for now: fall through to the lossy backlog
                pass
            except CHANNEL_ERRORS:
                # upstream closed the buffer: the lossy backlog is still
                # flushed before the connection is closed
                if not lossy_buffer:
                    break
            if data is None:
                # Priority 2: receive from lossy_buffer
                if lossy_buffer:
                    data = lossy_buffer.popleft()
                # wait new event
                else:
                    await self.send_event.wait()
                    continue
            # print(data, flush=True)

            # send message
            try:
                await self.ws.send_bytes(data)
                # send success, update activity
                self.last_active = anyio.current_time()
            except WEBSOCKET_ERRORS:
                # websocket disconnected
                # we capture and exit silently, so anyio will wait other task to finish current job
                break

        # confirm websocket is closed
        await self.close()
        # logger.info(f'{self} task_send closed')

    async def _task_wait_server_terminated(self, task_group: TaskGroup, out):
        """
        Args:
            task_group (TaskGroup):
            out (list[str]):
        """
        await WebsocketTopicServer.server_terminated.wait()
        # server terminated
        out.append('server')
        await self.close(code=1001, reason='Server shutdown')
        task_group.cancel_scope.cancel()

    async def _task_wait_conn_terminated(self, task_group: TaskGroup, out):
        """
        Args:
            task_group (TaskGroup):
            out (list[str]):
        """
        await self.conn_terminated.wait()
        # connection terminated
        out.append('conn')
        await self.close()
        task_group.cancel_scope.cancel()

    async def _wait_terminated(self, max_wait_time):
        """
        Args:
            max_wait_time (int | float):

        Returns:
            str: the waited event, or "" to keep connection
        """
        if max_wait_time <= 0:
            return ''
        out = []
        with anyio.move_on_after(max_wait_time):
            async with anyio.create_task_group() as task_group:
                task_group.start_soon(
                    self._task_wait_server_terminated, task_group, out
                )
                task_group.start_soon(self._task_wait_conn_terminated, task_group, out)
        if out:
            return out[0]
        else:
            return ''

    async def task_heartbeat(self):
        """
        Coroutine task that send "ping" to keep websocket alive if it idled for 30s
        """
        while True:
            now = anyio.current_time()
            next_ping = self.last_active + self.PING_INTERVAL
            max_wait_time = next_ping - now

            # wait until next ping time or server terminated
            if await self._wait_terminated(max_wait_time):
                break

            # woke up, check activity
            now = anyio.current_time()
            next_ping = self.last_active + self.PING_INTERVAL
            if now < next_ping:
                # we have activity during sleep, no need to ping for now
                continue

            # no activity, do ping
            self.pong_received = Event()
            try:
                success = await self.send(b'ping')
                # send success, update activity
                self.last_active = anyio.current_time()
            except WEBSOCKET_ERRORS:
                # websocket disconnected
                # we capture and exit silently, so anyio will wait other task to finish current job
                break
            if not success:
                break

            # wait pong
            with anyio.move_on_after(self.PONG_TIMEOUT) as cancel_scope:
                await self.pong_received.wait()

            # check if pong timeout
            if cancel_scope.cancelled_caught:
                await self.close(reason='Pong timeout')
                break

        # confirm websocket is closed
        await self.close()
        # logger.info(f'{self} task_heartbeat closed')

    async def handle_job(self, event: RequestEvent):
        """
        Dispatch request event to topic objects
        """
        op = event.o
        t = event.t
        if op == 'auth':
            # Electron token renewal: redeem the one-time code
            # issued by POST /api/ws/renew and update the connection's
            # auth_token to the latest token in the table. A failed
            # redeem raises AccessDenied: the connection stays alive.
            from oas.backend.ws.renew import renewal_manager

            if renewal_manager.redeem(event.v):
                self.auth_token = token_table.current()
                return
            raise AccessDenied('Invalid or expired renewal code')
        if op == 'sub':
            # cannot double subscribe a default-subscribed topic
            if t in self.DEFAULT_TOPIC_CLASS:
                return
            # check if topic valid
            try:
                topic_class = self.ALL_TOPIC_CLASS[t]
            except KeyError:
                raise AccessDenied(f'No such topic: "{t}"')
            # electron check before creating the topic: a rejected
            # subscribe only sends an error message and the connection
            # stays alive (red line: never close on subscribe
            # refusal, the frontend silently drops the error topic)
            if topic_class.REQUIRE_ELECTRON:
                if not token_table.verify(self.auth_token):
                    raise ElectronOnlyError(f'Topic requires electron: "{t}"')
            # if topic is already subscribed, ignore this event
            if t in self.subscribed:
                return
            # create new topic
            topic = topic_class(self.id, self)
            self.subscribed[t] = topic
            await topic.op_sub()
            return
        if op == 'unsub':
            # cannot unsubscribe a default-subscribed topic
            if t in self.DEFAULT_TOPIC_CLASS:
                return
            try:
                topic = self.subscribed.pop(t)
            except KeyError:
                # if topic is never subscribed, ignore this event
                return
            # remove topic
            await topic.op_unsub()
            return

        if op == 'rpc':
            # RPC calls must pair with RPC ID
            if not event.i:
                msg = 'Missing RPC ID in event'
                event = ResponseEvent(t='error', v=msg, i=event.i)
                await self.send(event)
                return
            # check if topic valid
            if t not in self.ALL_TOPIC_CLASS:
                msg = f'No such topic: "{t}"'
                event = ResponseEvent(t=t, v=msg, i=event.i)
                await self.send(event)
                return
            # check if topic subscribed
            try:
                topic = self.subscribed[t]
            except KeyError:
                # note that every RPC calls should have a Response with the same RPC ID
                # instead of just raising errors
                msg = f'Cannot do RPC before subscribing topic: "{t}"'
                event = ResponseEvent(t=event.t, v=msg, i=event.i)
                await self.send(event)
                return
            # do RPC call
            await topic.op_rpc(func=event.f, value=event.v, rpc_id=event.i)
            return

        raise AccessDenied(f'Operation not allowed: {op}')
