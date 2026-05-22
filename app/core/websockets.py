from __future__ import annotations

import asyncio
import logging
from fastapi import WebSocket

logger = logging.getLogger("fabouanes.websockets")


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.user_connections: dict[int, list[WebSocket]] = {}
        self.loop = None

    async def connect(self, websocket: WebSocket, user_id: int | None = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if user_id:
            self.user_connections.setdefault(user_id, []).append(websocket)
        if self.loop is None:
            self.loop = asyncio.get_running_loop()

    def disconnect(self, websocket: WebSocket, user_id: int | None = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if user_id:
            conns = self.user_connections.get(user_id, [])
            if websocket in conns:
                conns.remove(websocket)
            if not conns and user_id in self.user_connections:
                del self.user_connections[user_id]
        else:
            for uid, conns in list(self.user_connections.items()):
                if websocket in conns:
                    conns.remove(websocket)
                    if not conns:
                        del self.user_connections[uid]

    async def _send_to_connections(self, connections: list[WebSocket], message: str):
        for conn in list(connections):
            try:
                await conn.send_text(message)
            except Exception:
                self.disconnect(conn)

    def broadcast_sync(self, message: str):
        """Broadcast global — compatibilité descendante."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._send_to_connections(self.active_connections, message),
                self.loop,
            )

    def broadcast_to_user(self, user_id: int, message: str):
        """Envoie un message uniquement aux connexions de cet utilisateur."""
        conns = self.user_connections.get(user_id, [])
        if conns and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._send_to_connections(conns, message),
                self.loop,
            )


manager = ConnectionManager()
