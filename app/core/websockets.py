from __future__ import annotations

import asyncio
import logging
import json
import uuid
from fastapi import WebSocket

logger = logging.getLogger("fabouanes.websockets")

WORKER_ID = uuid.uuid4().hex


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.user_connections: dict[int, list[WebSocket]] = {}
        self.loop = None

    def startup(self):
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

    def shutdown(self):
        pass

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

    def _local_broadcast_global(self, message: str):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._send_to_connections(self.active_connections, message),
                self.loop,
            )

    def _local_broadcast_user(self, user_id: int, message: str):
        conns = self.user_connections.get(user_id, [])
        if conns and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._send_to_connections(conns, message),
                self.loop,
            )

    def broadcast_sync(self, message: str):
        """Broadcast global."""
        try:
            from app.core.db_helpers import execute_db
            payload = json.dumps({"type": "global", "message": message, "sender_id": WORKER_ID})
            execute_db(
                "INSERT INTO pubsub_events (channel, payload, sender_worker_id) VALUES (%s, %s, %s)",
                ("fabouanes:ws_broadcast", payload, WORKER_ID)
            )
        except Exception as e:
            logger.warning("DB pubsub websocket publish failed: %s", e)

        # Fallback local / run locally immediately
        self._local_broadcast_global(message)

    def broadcast_to_user(self, user_id: int, message: str):
        """Envoie un message uniquement aux connexions de cet utilisateur."""
        try:
            from app.core.db_helpers import execute_db
            payload = json.dumps({"type": "user", "user_id": user_id, "message": message, "sender_id": WORKER_ID})
            execute_db(
                "INSERT INTO pubsub_events (channel, payload, sender_worker_id) VALUES (%s, %s, %s)",
                ("fabouanes:ws_broadcast", payload, WORKER_ID)
            )
        except Exception as e:
            logger.warning("DB pubsub websocket user publish failed: %s", e)

        # Fallback local / run locally immediately
        self._local_broadcast_user(user_id, message)


manager = ConnectionManager()


def startup():
    manager.startup()


def shutdown():
    manager.shutdown()
