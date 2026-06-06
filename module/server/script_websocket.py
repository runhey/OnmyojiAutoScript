# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from typing import Iterable

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState


class ScriptWSManager:

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        # 等待连接
        await ws.accept()
        if ws not in self.active_connections:
            self.active_connections.append(ws)

    async def disconnect(self, ws: WebSocket):
        # 关闭时移除 ws 对象，重复调用也应安全
        if ws in self.active_connections:
            self.active_connections.remove(ws)
        if ws.client_state == WebSocketState.DISCONNECTED:
            return
        try:
            # 给前端发送最后一次关闭信号
            await ws.close()
        except (RuntimeError, WebSocketDisconnect):
            return
        except Exception:
            return

    async def send_text(self, ws: WebSocket, message: str) -> bool:
        return await self._send(ws, ws.send_text, message)

    async def send_json(self, ws: WebSocket, data: dict) -> bool:
        return await self._send(ws, ws.send_json, data)

    async def broadcast(self, message: str):
        # 广播消息
        await self._broadcast(self.active_connections, lambda connection: connection.send_text(message))

    async def broadcast_state(self, data: dict):
        # 广播自身的状态
        await self._broadcast(self.active_connections, lambda connection: connection.send_json(data))

    async def broadcast_log(self, log: str):
        # 广播日志
        await self._broadcast(self.active_connections, lambda connection: connection.send_text(log))

    async def _send(self, ws: WebSocket, sender, payload) -> bool:
        if ws.client_state == WebSocketState.DISCONNECTED:
            await self.disconnect(ws)
            return False
        try:
            await sender(payload)
            return True
        except (RuntimeError, WebSocketDisconnect):
            await self.disconnect(ws)
            return False
        except Exception:
            await self.disconnect(ws)
            return False

    async def _broadcast(self, connections: Iterable[WebSocket], sender_factory) -> None:
        dead_connections: list[WebSocket] = []
        for connection in list(connections):
            if connection.client_state == WebSocketState.DISCONNECTED:
                dead_connections.append(connection)
                continue
            try:
                await sender_factory(connection)
            except (RuntimeError, WebSocketDisconnect):
                dead_connections.append(connection)
            except Exception:
                dead_connections.append(connection)
        for connection in dead_connections:
            await self.disconnect(connection)




