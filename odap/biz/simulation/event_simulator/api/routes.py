from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List

from ..impl.event_generator import get_event_generator
from ..impl.timeline_engine import get_timeline_engine
from ..impl.scenario_template import get_scenario_template_manager
from ..services.simulator_service import EventSimulatorService

router = APIRouter(prefix="/api/event-simulator", tags=["event-simulator"])

event_generator = get_event_generator()
timeline_engine = get_timeline_engine()
template_manager = get_scenario_template_manager()
simulator_service = EventSimulatorService()


@router.post("/generate")
async def generate_event_sequence(body: Dict[str, Any] = None):
    try:
        data = body or {}
        result = event_generator.generate_event_sequence(
            template_id=data.get("template_id", "default"),
            workspace_id=data.get("workspace_id", "default"),
            count=data.get("count", 5),
            base_time=data.get("base_time"),
            entity_types=data.get("entity_types"),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inject")
async def inject_event(body: Dict[str, Any] = None):
    try:
        data = body or {}
        result = event_generator.inject_event(
            event_type=data.get("event_type", "unknown"),
            target_entity_type=data.get("target_entity_type", "entity"),
            data=data.get("data", {}),
            workspace_id=data.get("workspace_id", "default"),
            timestamp=data.get("timestamp"),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline/{timeline_id}")
async def get_timeline(timeline_id: str):
    try:
        result = timeline_engine.get_timeline(timeline_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timeline")
async def create_timeline(body: Dict[str, Any] = None):
    try:
        data = body or {}
        result = timeline_engine.create_timeline(
            timeline_id=data.get("timeline_id"),
            start_time=data.get("start_time"),
            speed=data.get("speed", 1.0),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clock/control")
async def control_clock(body: Dict[str, Any] = None):
    try:
        data = body or {}
        action = data.get("action", "")
        timeline_id = data.get("timeline_id", "")
        if not timeline_id:
            raise HTTPException(status_code=400, detail="timeline_id is required")

        if action == "start":
            result = timeline_engine.start_clock(timeline_id, data.get("speed", 1.0))
        elif action == "pause":
            result = timeline_engine.pause_clock(timeline_id)
        elif action == "resume":
            result = timeline_engine.resume_clock(timeline_id)
        elif action == "set_speed":
            result = timeline_engine.set_speed(timeline_id, data.get("speed", 1.0))
        elif action == "advance":
            result = timeline_engine.advance_time(timeline_id, data.get("real_seconds", 60.0))
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def list_templates(category: str = None):
    try:
        return {"templates": template_manager.list_templates(category)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    try:
        result = template_manager.get_template(template_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/templates")
async def create_template(body: Dict[str, Any] = None):
    try:
        data = body or {}
        result = template_manager.create_template(data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    try:
        result = template_manager.delete_template(template_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timelines")
async def list_timelines():
    try:
        return {"timelines": timeline_engine.list_timelines()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timeline/{timeline_id}/events")
async def inject_timeline_event(timeline_id: str, body: Dict[str, Any] = None):
    try:
        data = body or {}
        result = timeline_engine.inject_event_at_time(
            timeline_id=timeline_id,
            event=data.get("event", {}),
            target_time=data.get("target_time"),
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
