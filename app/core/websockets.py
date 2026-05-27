from __future__ import annotations

import asyncio
import logging
import os
import json
import uuid
from fastapi import WebSocket

logger = logging.getLogger("fabouanes.websockets")

WORKER_ID = uuid.uuid4().hex
REDIS_URL = os.environ.get("REDIS_URL", "").strip()

_redis_client = None
if REDIS_URL:  # pragma: no cover
    try:
        import redis
        _redis_client = redis.from_url(REDIS_URL)
        _redis_client.ping()
    except Exception as e:
        logger.warning("Failed to connect to Redis for WebSockets, falling back to in-memory: %s", e)
        _redis_client = None


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.user_connections: dict[int, list[WebSocket]] = {}
        self.loop = None
        self._redis_thread = None

    def startup(self):
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        self._start_redis_listener()

    def shutdown(self):  # pragma: no cover
        if self._redis_thread:
            try:
                self._redis_thread.stop()
                logger.info("Redis WebSocket subscriber stopped.")
            except Exception:
                pass

    def _start_redis_listener(self):  # pragma: no cover
        if not _redis_client:
            return
        try:
            pubsub = _redis_client.pubsub()
            pubsub.subscribe(**{"fabouanes:ws_broadcast": self._redis_message_handler})
            self._redis_thread = pubsub.run_in_thread(sleep_time=0.1, daemon=True)
            logger.info("Redis WebSocket subscriber started (worker_id=%s)", WORKER_ID)
        except Exception as e:
            logger.error("Failed to start Redis WebSocket subscriber: %s", e)

    def _redis_message_handler(self, message):  # pragma: no cover
        try:
            if message["type"] != "message":
                return
            data_str = message["data"]
            if isinstance(data_str, bytes):
                data_str = data_str.decode("utf-8")
            data = json.loads(data_str)
            msg_type = data.get("type")
            msg = data.get("message")
            if msg_type == "global":
                self._local_broadcast_global(msg)
            elif msg_type == "user":
                user_id = data.get("user_id")
                if user_id is not None:
                    self._local_broadcast_user(int(user_id), msg)
        except Exception as e:
            logger.exception("Error handling Redis WebSocket message")

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
        """Broadcast global — compatibilité descendante."""
        if _redis_client:  # pragma: no cover
            try:
                payload = json.dumps({"type": "global", "message": message})
                _redis_client.publish("fabouanes:ws_broadcast", payload)
                return
            except Exception as e:
                logger.warning("Redis websocket publish failed: %s", e)
        # Fallback local
        self._local_broadcast_global(message)

    def broadcast_to_user(self, user_id: int, message: str):
        """Envoie un message uniquement aux connexions de cet utilisateur."""
        if _redis_client:  # pragma: no cover
            try:
                payload = json.dumps({"type": "user", "user_id": user_id, "message": message})
                _redis_client.publish("fabouanes:ws_broadcast", payload)
                return
            except Exception as e:
                logger.warning("Redis websocket user publish failed: %s", e)
        # Fallback local
        self._local_broadcast_user(user_id, message)


manager = ConnectionManager()


def startup():
    manager.startup()


def shutdown():
    manager.shutdown()

