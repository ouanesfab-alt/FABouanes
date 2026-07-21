from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, Request
from app.core.websockets import manager
from app.utils.api_response import APIResponse
from collections import defaultdict
import logging

logger = logging.getLogger("fabouanes.api.ws")
router = APIRouter(prefix="/api/v1")

MAX_ACTIVE_WS_CONNECTIONS = 50
MAX_CONNECTIONS_PER_IP = 10
_ws_ip_counts: dict[str, int] = defaultdict(int)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_ip = websocket.client.host if websocket.client else "unknown"

    # Enforce global and per-IP connection limits
    if len(manager.active_connections) >= MAX_ACTIVE_WS_CONNECTIONS:
        logger.warning("WebSocket Rejected: Global connection limit reached (%s)", MAX_ACTIVE_WS_CONNECTIONS)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Global connection limit reached.")
        return

    if _ws_ip_counts[client_ip] >= MAX_CONNECTIONS_PER_IP:
        logger.warning("WebSocket Rejected: IP %s connection limit reached (%s)", client_ip, MAX_CONNECTIONS_PER_IP)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Per-IP connection limit reached.")
        return

    _ws_ip_counts[client_ip] += 1
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error for %s: %s", client_ip, e)
        manager.disconnect(websocket)
    finally:
        _ws_ip_counts[client_ip] = max(0, _ws_ip_counts[client_ip] - 1)



@router.get("/session/ping")
async def session_ping(request: Request):
    """Silent keep-alive endpoint for updating session cookies during user activity."""
    user_id = request.session.get("user_id")
    return APIResponse.success(data={"active": bool(user_id)})


