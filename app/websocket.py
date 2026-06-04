import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = structlog.get_logger()
router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                log.error("websocket.broadcast_error", error=str(e))
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't really expect client messages, just keep connection open
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
