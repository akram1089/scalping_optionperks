import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi import Depends

from app.auth.jwt import decode_token
from app.broker.ticker_service import INDEX_DISPLAY_SYMBOLS
from app.broker.ticker import RedisPubSub

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
_relay_task: asyncio.Task | None = None


async def _redis_relay() -> None:
    try:
        pubsub = await RedisPubSub.subscribe()
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = json.loads(message["data"])
            await manager.broadcast({"type": "tick", "data": data})
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Redis relay error")


@router.websocket("/ws/live")
async def websocket_live(ws: WebSocket, token: str | None = None):
    if token:
        try:
            decode_token(token, "access")
        except Exception:
            await ws.close(code=4001)
            return
    await manager.connect(ws)
    for sym in INDEX_DISPLAY_SYMBOLS:
        cached = await RedisPubSub.get_tick(sym)
        if cached:
            await ws.send_json({"type": "tick", "data": cached})
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(ws)


async def start_relay() -> None:
    global _relay_task
    _relay_task = asyncio.create_task(_redis_relay())


async def stop_relay() -> None:
    global _relay_task
    if _relay_task:
        _relay_task.cancel()
        try:
            await _relay_task
        except asyncio.CancelledError:
            pass
