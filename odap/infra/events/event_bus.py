"""DomainEventBus — WebSocket 事件总线

从 odap.web.ws.event_bus 中提取，供 infra 层和 web 层共享引用。
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Any, Optional, Callable, Awaitable
from collections import defaultdict

logger = logging.getLogger(__name__)


class DomainEventBus:
    def __init__(self):
        self._ws_clients: Set = set()
        self._workspace_clients: Dict[str, Set] = defaultdict(set)
        self._subscribers: Dict[str, list] = defaultdict(list)
        self._event_history: list = []
        self._max_history = 1000

    async def connect(self, websocket, workspace_id: Optional[str] = None):
        await websocket.accept()
        self._ws_clients.add(websocket)
        if workspace_id:
            self._workspace_clients[workspace_id].add(websocket)
        logger.info(f"WebSocket client connected, total: {len(self._ws_clients)}, workspace: {workspace_id}")

    def disconnect(self, websocket, workspace_id: Optional[str] = None):
        self._ws_clients.discard(websocket)
        if workspace_id:
            self._workspace_clients[workspace_id].discard(websocket)
        logger.info(f"WebSocket client disconnected, total: {len(self._ws_clients)}")

    async def emit(self, event_type: str, data: dict, workspace_id: Optional[str] = None):
        message = json.dumps({
            "type": event_type,
            "data": data,
            "workspace_id": workspace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, default=str, ensure_ascii=False)

        self._event_history.append({"type": event_type, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()})
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        await self._broadcast(message, workspace_id)

        for callback in self._subscribers.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, data, workspace_id)
                else:
                    callback(event_type, data, workspace_id)
            except Exception as e:
                logger.warning(f"Event subscriber error for {event_type}: {e}")

    def subscribe(self, event_type: str, callback: Callable):
        self._subscribers[event_type].append(callback)

    async def emit_entity_changed(self, entity_id: str, entity_type: str, change_type: str,
                                   properties: dict, workspace_id: Optional[str] = None):
        await self.emit("entity:changed", {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "change_type": change_type,
            "properties": properties,
        }, workspace_id)

    async def emit_intel_updated(self, report_id: str, source: str, confidence: float,
                                  summary: str, workspace_id: Optional[str] = None):
        await self.emit("intel:updated", {
            "report_id": report_id,
            "source": source,
            "confidence": confidence,
            "summary": summary,
        }, workspace_id)

    async def emit_action_result(self, action_id: str, action_type: str, target_id: str,
                                  status: str, result: dict, workspace_id: Optional[str] = None):
        await self.emit("action:result", {
            "action_id": action_id,
            "action_type": action_type,
            "target_id": target_id,
            "status": status,
            "result": result,
        }, workspace_id)

    async def emit_oadp_progress(self, phase: str, status: str, agent: str,
                                  data: Optional[dict] = None, workspace_id: Optional[str] = None):
        await self.emit("oadp:progress", {
            "phase": phase,
            "status": status,
            "agent": agent,
            "data": data or {},
        }, workspace_id)

    async def emit_opa_check(self, action: str, allowed: bool, reason: str,
                              workspace_id: Optional[str] = None):
        await self.emit("opa:check", {
            "action": action,
            "allowed": allowed,
            "reason": reason,
        }, workspace_id)

    async def emit_audit_event(self, event_type: str, actor: str, action: str,
                                result: str, workspace_id: Optional[str] = None):
        await self.emit("audit:event", {
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "result": result,
        }, workspace_id)

    async def emit_decision_step(self, decision_id: str, phase: str, description: str,
                                  evidence: Optional[list] = None, workspace_id: Optional[str] = None):
        await self.emit("decision:step", {
            "decision_id": decision_id,
            "phase": phase,
            "description": description,
            "evidence": evidence or [],
        }, workspace_id)

    async def emit_decision_completed(self, decision_id: str, reasoning: str,
                                       evidence: Optional[list] = None, workspace_id: Optional[str] = None):
        await self.emit("decision:completed", {
            "decision_id": decision_id,
            "reasoning": reasoning,
            "evidence": evidence or [],
        }, workspace_id)

    async def emit_simulation_progress(
        self,
        simulation_id: str,
        phase: str,
        progress: float,
        status: str,
        data: Optional[dict] = None,
        workspace_id: Optional[str] = None,
    ):
        await self.emit("simulation:progress", {
            "simulation_id": simulation_id,
            "phase": phase,
            "progress": progress,
            "status": status,
            "data": data or {},
        }, workspace_id)

    async def emit_simulation_completed(
        self,
        simulation_id: str,
        results: dict,
        workspace_id: Optional[str] = None,
    ):
        await self.emit("simulation:completed", {
            "simulation_id": simulation_id,
            "results": results,
        }, workspace_id)

    async def emit_simulation_failed(
        self,
        simulation_id: str,
        error: str,
        workspace_id: Optional[str] = None,
    ):
        await self.emit("simulation:failed", {
            "simulation_id": simulation_id,
            "error": error,
        }, workspace_id)

    async def _broadcast(self, message: str, workspace_id: Optional[str] = None):
        dead: Set = set()
        targets = self._workspace_clients.get(workspace_id, set()) if workspace_id else self._ws_clients
        if not workspace_id:
            targets = self._ws_clients

        for ws in list(targets):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)

        self._ws_clients -= dead
        for wid in self._workspace_clients:
            self._workspace_clients[wid] -= dead

    def get_stats(self) -> dict:
        return {
            "total_clients": len(self._ws_clients),
            "workspace_clients": {k: len(v) for k, v in self._workspace_clients.items()},
            "event_types": list(self._subscribers.keys()),
            "history_size": len(self._event_history),
        }

    def get_recent_events(self, limit: int = 50) -> list:
        return self._event_history[-limit:]


event_bus = DomainEventBus()


def get_event_bus() -> DomainEventBus:
    return event_bus
