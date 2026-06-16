"""WebSocket 路由定义"""

import asyncio
import json as _json
from typing import Optional, Set

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


# ── 本体构建进度 WebSocket ──────────────────────────────────────────

# 全局订阅者集合：所有连接到构建进度的 WebSocket 客户端
_build_progress_clients: Set[WebSocket] = set()


@ws_router.websocket("/ws/ontology/build-progress")
async def ontology_build_progress(websocket: WebSocket):
    """本体构建进度 WebSocket 端点。

    客户端连接后可实时接收管道各阶段的进度推送。
    消息格式:
    {
        "type": "build_progress",
        "data": {
            "stage": "collection|cleaning|llm|ontology|version|graph",
            "progress": 0.0 ~ 100.0,
            "message": "执行中: collection",
            "ingest_id": "...",
            "scenario_id": "..."
        }
    }
    """
    await websocket.accept()
    _build_progress_clients.add(websocket)

    # 注册到 DomainEventBus，订阅 ontology:build_progress 事件
    from odap.infra.events.event_bus import get_event_bus
    bus = get_event_bus()

    async def _on_build_progress(event_type: str, data: dict, workspace_id: Optional[str] = None):
        """当收到 ontology:build_progress 事件时，推送给此客户端"""
        try:
            await websocket.send_text(_json.dumps({
                "type": "build_progress",
                "data": data,
            }, default=str, ensure_ascii=False))
        except Exception:
            pass

    bus.subscribe("ontology:build_progress", _on_build_progress)

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                msg = _json.loads(raw) if raw else {}
                msg_type = msg.get("type", "")
                if msg_type == "ping":
                    await websocket.send_text(_json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text('{"type":"heartbeat"}')
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        _build_progress_clients.discard(websocket)


async def emit_build_progress(
    stage: str,
    progress: float,
    message: str,
    ingest_id: str = "",
    scenario_id: str = "",
):
    """向所有构建进度订阅者推送进度事件。

    此函数可被 IngestService / PipelineService 的 progress_callback 调用。
    """
    from odap.infra.events.event_bus import get_event_bus
    bus = get_event_bus()
    await bus.emit("ontology:build_progress", {
        "stage": stage,
        "progress": progress,
        "message": message,
        "ingest_id": ingest_id,
        "scenario_id": scenario_id,
    })
