"""WebSocket 路由定义"""

import asyncio
import json as _json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter()


@ws_router.websocket("/ws/agent/decisions")
async def agent_decisions_ws(websocket: WebSocket, workspace_id: Optional[str] = None):
    from odap.web.ws.event_bus import get_event_bus
    bus = get_event_bus()
    await bus.connect(websocket, workspace_id)
    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                msg = _json.loads(raw) if raw else {}
                msg_type = msg.get("type", "")
                if msg_type == "ping":
                    await websocket.send_text(_json.dumps({"type": "pong"}))
                elif msg_type == "subscribe":
                    pass
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text('{"type":"heartbeat"}')
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        bus.disconnect(websocket, workspace_id)


@ws_router.websocket("/ws/ontology/edit-lock/{ontology_id}")
async def edit_lock_ws(websocket: WebSocket, ontology_id: str, user_id: str = ""):
    from odap.web.ws.edit_lock_handler import edit_lock_websocket_handler
    await edit_lock_websocket_handler(websocket, ontology_id, user_id)


@ws_router.websocket("/ws/simulation/progress")
async def simulation_progress_ws(websocket: WebSocket, workspace_id: Optional[str] = None):
    from odap.web.ws.event_bus import get_event_bus
    bus = get_event_bus()
    await bus.connect(websocket, workspace_id)
    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                msg = _json.loads(raw) if raw else {}
                msg_type = msg.get("type", "")
                if msg_type == "ping":
                    await websocket.send_text(_json.dumps({"type": "pong"}))
                elif msg_type == "subscribe":
                    pass
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text('{"type":"heartbeat"}')
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        bus.disconnect(websocket, workspace_id)
