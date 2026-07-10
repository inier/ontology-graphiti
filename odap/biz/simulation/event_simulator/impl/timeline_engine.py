import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


def _tl_audit(action: str, *, result_status: str = "success",
              result_message: str = "", resource: str = None,
              details: Dict[str, Any] = None) -> None:
    """Timeline Engine 审计便捷函数：失败仅 warning，不阻断业务"""
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="event_simulator",
        )
    except Exception as e:
        logger.warning(f"Audit write failed (timeline) action={action}: {e}")


class ClockState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


class TimelineEngine:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._timelines: Dict[str, Dict[str, Any]] = {}
        self._event_queue: Dict[str, List[Dict[str, Any]]] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._storage = None
        try:
            from ..storage import SQLiteEventStorage
            self._storage = SQLiteEventStorage()
        except Exception:
            logger.warning("SQLiteEventStorage not available, using in-memory only")
        self._initialized = True

    def create_timeline(
        self,
        timeline_id: Optional[str] = None,
        start_time: Optional[str] = None,
        speed: float = 1.0,
    ) -> Dict[str, Any]:
        tid = timeline_id or f"timeline_{uuid.uuid4().hex[:8]}"
        timeline = {
            "timeline_id": tid,
            "clock_state": ClockState.STOPPED.value,
            "simulation_speed": speed,
            "current_time": start_time or datetime.now(timezone.utc).isoformat(),
            "start_time": start_time or datetime.now(timezone.utc).isoformat(),
            "elapsed_sim_seconds": 0.0,
            "events_injected": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._timelines[tid] = timeline
        self._event_queue[tid] = []
        self._callbacks[tid] = []

        if self._storage:
            try:
                self._storage.save_timeline({
                    "timeline_id": tid,
                    "clock_state": timeline["clock_state"],
                    "start_time": timeline["start_time"],
                    "current_time": timeline["current_time"],
                    "speed": timeline["simulation_speed"],
                    "events": [],
                })
            except Exception:
                logger.warning("Failed to persist timeline to storage")

        return {
            "timeline_id": tid,
            "clock_state": timeline["clock_state"],
            "simulation_speed": timeline["simulation_speed"],
            "current_time": timeline["current_time"],
        }

    def start_clock(self, timeline_id: str, speed: float = 1.0) -> Dict[str, Any]:
        timeline = self._timelines.get(timeline_id)
        if not timeline:
            return {"status": "error", "message": f"Timeline {timeline_id} not found"}
        timeline["clock_state"] = ClockState.RUNNING.value
        timeline["simulation_speed"] = speed
        self._persist_timeline(timeline_id)
        return {
            "timeline_id": timeline_id,
            "clock_state": timeline["clock_state"],
            "simulation_speed": timeline["simulation_speed"],
            "current_time": timeline["current_time"],
        }

    def pause_clock(self, timeline_id: str) -> Dict[str, Any]:
        timeline = self._timelines.get(timeline_id)
        if not timeline:
            return {"status": "error", "message": f"Timeline {timeline_id} not found"}
        timeline["clock_state"] = ClockState.PAUSED.value
        self._persist_timeline(timeline_id)
        return {
            "timeline_id": timeline_id,
            "clock_state": timeline["clock_state"],
            "current_time": timeline["current_time"],
        }

    def resume_clock(self, timeline_id: str) -> Dict[str, Any]:
        timeline = self._timelines.get(timeline_id)
        if not timeline:
            return {"status": "error", "message": f"Timeline {timeline_id} not found"}
        timeline["clock_state"] = ClockState.RUNNING.value
        self._persist_timeline(timeline_id)
        return {
            "timeline_id": timeline_id,
            "clock_state": timeline["clock_state"],
            "simulation_speed": timeline["simulation_speed"],
            "current_time": timeline["current_time"],
        }

    def set_speed(self, timeline_id: str, speed: float) -> Dict[str, Any]:
        timeline = self._timelines.get(timeline_id)
        if not timeline:
            return {"status": "error", "message": f"Timeline {timeline_id} not found"}
        if speed <= 0:
            return {"status": "error", "message": "Speed must be positive"}
        timeline["simulation_speed"] = speed
        self._persist_timeline(timeline_id)
        return {
            "timeline_id": timeline_id,
            "simulation_speed": speed,
            "current_time": timeline["current_time"],
        }

    def advance_time(self, timeline_id: str, real_seconds: float) -> Dict[str, Any]:
        timeline = self._timelines.get(timeline_id)
        if not timeline:
            _tl_audit(
                "event_tick_run",
                result_status="failure",
                resource=timeline_id,
                result_message="Timeline not found",
                details={"timeline_id": timeline_id},
            )
            return {"status": "error", "message": f"Timeline {timeline_id} not found"}

        sim_seconds = real_seconds * timeline["simulation_speed"]
        timeline["elapsed_sim_seconds"] += sim_seconds

        current = datetime.fromisoformat(timeline["current_time"])
        advanced = current + timedelta(seconds=sim_seconds)
        timeline["current_time"] = advanced.isoformat()

        triggered = self._process_events(timeline_id)
        events_count = len(triggered)
        self._persist_timeline(timeline_id)

        _tl_audit(
            "event_tick_run",
            result_status="success",
            resource=timeline_id,
            details={
                "timeline_id": timeline_id,
                "events_count": events_count,
                "advanced_sim_seconds": round(sim_seconds, 2),
                "generated_entity_deltas_count": events_count,
                "affected_relations_count": events_count,
            },
        )
        return {
            "timeline_id": timeline_id,
            "current_time": timeline["current_time"],
            "advanced_sim_seconds": sim_seconds,
            "events_triggered": triggered,
        }

    def inject_event_at_time(
        self,
        timeline_id: str,
        event: Dict[str, Any],
        target_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        if timeline_id not in self._timelines:
            _tl_audit(
                "event_ingest",
                result_status="failure",
                resource=timeline_id,
                result_message="Timeline not found",
                details={"timeline_id": timeline_id},
            )
            return {"status": "error", "message": f"Timeline {timeline_id} not found"}

        event_entry = {
            "event_id": event.get("event_id", f"evt_{uuid.uuid4().hex[:8]}"),
            "event_type": event.get("event_type", "unknown"),
            "target_time": target_time or self._timelines[timeline_id]["current_time"],
            "data": event.get("data", {}),
            "status": "queued",
            "injected_at": datetime.now(timezone.utc).isoformat(),
        }
        self._event_queue[timeline_id].append(event_entry)
        self._timelines[timeline_id]["events_injected"] += 1
        generated_entity_deltas_count = sum(
            1 for k in event.get("data", {}).keys() if "delta" in k.lower()
        )
        _tl_audit(
            "event_ingest",
            result_status="success",
            resource=event_entry["event_id"],
            details={
                "timeline_id": timeline_id,
                "event_id": event_entry["event_id"],
                "event_type": event_entry["event_type"],
                "events_count": 1,
                "generated_entity_deltas_count": generated_entity_deltas_count,
                "affected_relations_count": 1,
            },
        )
        return {
            "event_id": event_entry["event_id"],
            "status": "queued",
            "target_time": event_entry["target_time"],
        }

    def get_timeline(self, timeline_id: str) -> Dict[str, Any]:
        timeline = self._timelines.get(timeline_id)
        if not timeline:
            return {"status": "error", "message": f"Timeline {timeline_id} not found"}
        events = self._event_queue.get(timeline_id, [])
        return {
            **timeline,
            "queued_events": len(events),
            "events": events,
        }

    def list_timelines(self) -> List[Dict[str, Any]]:
        return [
            {
                "timeline_id": t["timeline_id"],
                "clock_state": t["clock_state"],
                "simulation_speed": t["simulation_speed"],
                "current_time": t["current_time"],
                "events_injected": t["events_injected"],
            }
            for t in self._timelines.values()
        ]

    def _persist_timeline(self, timeline_id: str):
        if not self._storage:
            return
        timeline = self._timelines.get(timeline_id)
        if not timeline:
            return
        try:
            self._storage.save_timeline({
                "timeline_id": timeline_id,
                "clock_state": timeline["clock_state"],
                "start_time": timeline["start_time"],
                "current_time": timeline["current_time"],
                "speed": timeline["simulation_speed"],
                "events": self._event_queue.get(timeline_id, []),
            })
        except Exception:
            logger.warning("Failed to persist timeline to storage")

    def _process_events(self, timeline_id: str) -> List[str]:
        timeline = self._timelines.get(timeline_id)
        if not timeline:
            return []

        current_time = timeline["current_time"]
        triggered = []
        remaining = []

        for event in self._event_queue.get(timeline_id, []):
            if event["target_time"] <= current_time and event["status"] == "queued":
                event["status"] = "triggered"
                event["triggered_at"] = datetime.now(timezone.utc).isoformat()
                triggered.append(event["event_id"])
                for callback in self._callbacks.get(timeline_id, []):
                    try:
                        callback(event)
                    except Exception as e:
                        logger.warning(f"Timeline callback error: {e}")
            else:
                remaining.append(event)

        self._event_queue[timeline_id] = remaining + [
            e for e in self._event_queue.get(timeline_id, []) if e["status"] == "triggered"
        ]
        return triggered

    def register_callback(self, timeline_id: str, callback: Callable) -> Dict[str, Any]:
        if timeline_id not in self._callbacks:
            return {"status": "error", "message": f"Timeline {timeline_id} not found"}
        self._callbacks[timeline_id].append(callback)
        return {"status": "ok", "timeline_id": timeline_id}


def get_timeline_engine() -> TimelineEngine:
    return TimelineEngine()
