"""WebSocket endpoint for real-time progress streaming via Redis pub/sub."""

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings

router = APIRouter()


@router.websocket("/ws/progress/{session_id}")
async def ws_progress(websocket: WebSocket, session_id: str):
    await websocket.accept()
    settings = get_settings()
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        # Send latest cached state for late joiners
        cached = await r.get(f"progress_state:{session_id}")
        if cached:
            await websocket.send_text(cached)

        # Subscribe to all task progress channels for this session
        pubsub = r.pubsub()
        await pubsub.psubscribe(f"progress:*")

        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] == "pmessage":
                try:
                    data = json.loads(msg["data"])
                    await websocket.send_text(json.dumps(data))
                except (json.JSONDecodeError, TypeError):
                    pass

            # Check if client is still connected by sending a ping
            try:
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.01,
                )
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe()
        await r.aclose()
