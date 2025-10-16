# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

class ScriptWSManager:

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        # 等待连接
        await ws.accept()
        self.active_connections.append(ws)

    async def disconnect(self, ws: WebSocket):
        # 关闭时 移除ws对象
        self.active_connections.remove(ws)
        try:
            # 给前端发送最后一次关闭信号
            await ws.close()
        except RuntimeError as e:
            print(e)

    async def broadcast(self, message: str):
        # 广播消息
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except RuntimeError:
                await self.disconnect(connection)

    async def broadcast_state(self, data: dict):
        # 广播自身的状态
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except RuntimeError:
                await self.disconnect(connection)

    async def broadcast_log(self, log: str):
        # 广播日志
        for connection in self.active_connections:
            try:
                await connection.send_text(log)
            except RuntimeError:
                await self.disconnect(connection)





