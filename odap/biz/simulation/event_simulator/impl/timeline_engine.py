import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


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
        return {
            "timeline_id": timeline_id,
            "simulation_speed": speed,
            "current_time": timeline["current_time"],
        }

    def advance_time(self, timeline_id: str, real_seconds: float) -> Dict[str, Any]:
        timeline = self._timelines.get(timeline_id)
        if not timeline:
            return {"status": "error", "message": f"Timeline {timeline_id} not found"}

        sim_seconds = real_seconds * timeline["simulation_speed"]
        timeline["elapsed_sim_seconds"] += sim_seconds

        current = datetime.fromisoformat(timeline["current_time"])
        advanced = current + timedelta(seconds=sim_seconds)
        timeline["current_time"] = advanced.isoformat()

        triggered = self._process_events(timeline_id)

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
