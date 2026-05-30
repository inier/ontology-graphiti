import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from .storage import SharedMemoryStorage
from .models.types import SharedEventType


class SharedMemoryService:
    _instance = None

    @classmethod
    def get_instance(cls, storage=None):
        if cls._instance is None:
            cls._instance = cls(storage)
        return cls._instance

    def __init__(self, storage=None):
        self.storage = storage or SharedMemoryStorage()

    def create_context(self, name, description="", scenario_id=None, session_id=None,
                       initial_state=None):
        context_id = f"ctx-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        ctx_data = {
            "context_id": context_id, "name": name, "description": description,
            "scenario_id": scenario_id, "session_id": session_id,
            "shared_state": initial_state or {}, "version": 1,
            "is_active": True, "created_at": now, "updated_at": now
        }
        self.storage.save_context(ctx_data)
        return {"status": "success", "context_id": context_id, "name": name, "version": 1}

    def get_context(self, context_id):
        data = self.storage.get_context(context_id)
        if not data:
            return {"status": "error", "message": "Context not found"}
        result = dict(data)
        if isinstance(result.get("shared_state"), str):
            result["shared_state"] = json.loads(result["shared_state"])
        return {"status": "success", **result}

    def list_contexts(self, scenario_id=None, is_active=None):
        contexts = self.storage.list_contexts(scenario_id, is_active)
        return {"status": "success", "count": len(contexts),
                "contexts": [{"context_id": c["context_id"], "name": c["name"],
                              "scenario_id": c.get("scenario_id"),
                              "version": c.get("version", 1)} for c in contexts]}

    def delete_context(self, context_id):
        result = self.storage.delete_context(context_id)
        if not result:
            return {"status": "error", "message": "Context not found"}
        return {"status": "success", "context_id": context_id}

    def update_shared_state(self, context_id, agent_id, updates):
        ctx = self.storage.get_context(context_id)
        if not ctx:
            return {"status": "error", "message": "Context not found"}
        shared_state = json.loads(ctx.get("shared_state", "{}"))
        conflicts = []
        for key, value in updates.items():
            if key in shared_state:
                existing = shared_state[key]
                if isinstance(existing, dict) and existing.get("updated_by") != agent_id:
                    existing_time = existing.get("updated_at", "")
                    new_time = datetime.now().isoformat()
                    if existing_time > new_time:
                        conflicts.append(key)
                        continue
            shared_state[key] = {"value": value, "updated_by": agent_id,
                                 "updated_at": datetime.now().isoformat()}
        ctx["shared_state"] = shared_state
        ctx["version"] = ctx.get("version", 1) + 1
        ctx["updated_at"] = datetime.now().isoformat()
        self.storage.save_context(dict(ctx))
        self._emit_event(context_id, agent_id, SharedEventType.STATE_UPDATE,
                        {"updates": list(updates.keys()), "conflicts": conflicts})
        return {"status": "success", "context_id": context_id,
                "version": ctx["version"], "conflicts": conflicts}

    def read_shared_state(self, context_id, keys=None):
        ctx = self.storage.get_context(context_id)
        if not ctx:
            return {"status": "error", "message": "Context not found"}
        shared_state = json.loads(ctx.get("shared_state", "{}"))
        if keys:
            shared_state = {k: v for k, v in shared_state.items() if k in keys}
        return {"status": "success", "context_id": context_id,
                "shared_state": shared_state, "version": ctx.get("version", 1)}

    def join_context(self, context_id, agent_id, agent_role=""):
        ctx = self.storage.get_context(context_id)
        if not ctx:
            return {"status": "error", "message": "Context not found"}
        existing = self.storage.get_agent_state(context_id, agent_id)
        if existing:
            return {"status": "success", "message": "Already joined"}
        now = datetime.now().isoformat()
        state_data = {
            "state_id": f"as-{uuid.uuid4().hex[:8]}", "context_id": context_id,
            "agent_id": agent_id, "agent_role": agent_role,
            "state_data": {}, "last_heartbeat": now,
            "is_active": True, "created_at": now, "updated_at": now
        }
        self.storage.save_agent_state(state_data)
        self._emit_event(context_id, agent_id, SharedEventType.STATE_UPDATE,
                        {"action": "joined", "role": agent_role})
        return {"status": "success", "context_id": context_id, "agent_id": agent_id}

    def leave_context(self, context_id, agent_id):
        existing = self.storage.get_agent_state(context_id, agent_id)
        if not existing:
            return {"status": "error", "message": "Agent not in context"}
        existing["is_active"] = 0
        existing["updated_at"] = datetime.now().isoformat()
        self.storage.save_agent_state(dict(existing))
        self._emit_event(context_id, agent_id, SharedEventType.STATE_UPDATE,
                        {"action": "left"})
        return {"status": "success", "context_id": context_id, "agent_id": agent_id}

    def heartbeat(self, context_id, agent_id, state_data=None):
        existing = self.storage.get_agent_state(context_id, agent_id)
        if not existing:
            return {"status": "error", "message": "Agent not in context"}
        now = datetime.now().isoformat()
        existing["last_heartbeat"] = now
        existing["updated_at"] = now
        if state_data:
            existing["state_data"] = json.dumps(state_data, ensure_ascii=False)
        self.storage.save_agent_state(dict(existing))
        return {"status": "success", "heartbeat_at": now}

    def get_agent_states(self, context_id):
        states = self.storage.list_agent_states(context_id)
        return {"status": "success", "context_id": context_id,
                "agents": [{"agent_id": s["agent_id"], "agent_role": s.get("agent_role", ""),
                            "last_heartbeat": s.get("last_heartbeat", ""),
                            "state_data": json.loads(s.get("state_data", "{}"))}
                           for s in states]}

    def get_pending_events(self, context_id, agent_id=None, limit=100):
        events = self.storage.get_pending_events(context_id, agent_id, limit)
        return {"status": "success", "count": len(events),
                "events": [{"event_id": e["event_id"], "event_type": e["event_type"],
                            "agent_id": e["agent_id"],
                            "event_data": json.loads(e.get("event_data", "{}")),
                            "created_at": e["created_at"]} for e in events]}

    def consume_event(self, event_id):
        result = self.storage.consume_event(event_id)
        if not result:
            return {"status": "error", "message": "Event not found"}
        return {"status": "success", "event_id": event_id}

    def request_consensus(self, context_id, agent_id, topic, proposal):
        self._emit_event(context_id, agent_id, SharedEventType.CONSENSUS_REQUEST,
                        {"topic": topic, "proposal": proposal})
        return {"status": "success", "message": "Consensus request broadcast"}

    def vote_consensus(self, context_id, agent_id, topic, vote, reason=""):
        self._emit_event(context_id, agent_id, SharedEventType.CONSENSUS_REACHED,
                        {"topic": topic, "vote": vote, "reason": reason})
        return {"status": "success", "message": "Vote recorded"}

    def _emit_event(self, context_id, agent_id, event_type, event_data):
        event = {
            "event_id": f"evt-{uuid.uuid4().hex[:8]}",
            "context_id": context_id, "agent_id": agent_id,
            "event_type": event_type.value if hasattr(event_type, "value") else event_type,
            "event_data": event_data, "created_at": datetime.now().isoformat()
        }
        self.storage.save_event(event)


get_shared_memory_service = SharedMemoryService.get_instance
