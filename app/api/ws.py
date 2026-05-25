from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websockets import manager
import logging

logger = logging.getLogger("fabouanes.api.ws")
router = APIRouter(prefix="/api/v1")

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect any client -> server messages right now,
            # but we need to listen to detect disconnections.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error", extra={"error": str(e)})
        manager.disconnect(websocket)
