from fastapi import APIRouter, HTTPException, Body, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Optional, Dict, Any, List

from .schemas import (
    PerceptionEvent, PerceptionOutput, PerceptionSourceType,
    PerceptionPriority, ObserverConfig,
)
from .hub import get_perception_hub

router = APIRouter(prefix="/api/perception", tags=["perception"])


@router.post("/ingest", response_model=PerceptionOutput)
async def ingest_perception(event: PerceptionEvent,
    user=Depends(get_current_user)):
    hub = get_perception_hub()
    return await hub.process_event(event)


@router.post("/ingest/manual")
async def ingest_manual(
    content: str = Body(..., embed=True),
    source_type: PerceptionSourceType = Body(PerceptionSourceType.MANUAL, embed=True),
    metadata: Optional[Dict[str, Any]] = Body(None, embed=True),
    user=Depends(get_current_user)):
    hub = get_perception_hub()
    event = hub.ingest_manual(content, source_type, metadata)
    return await hub.process_event(event)


@router.post("/ingest/webhook")
async def ingest_webhook(
    payload: Dict[str, Any] = Body(...),
    user=Depends(get_current_user)):
    hub = get_perception_hub()
    event_id = hub.ingest_webhook(payload)
    event = PerceptionEvent(
        event_id=event_id,
        source_type=PerceptionSourceType.WEBHOOK,
        source_name="webhook",
        raw_content=str(payload),
        structured_data=payload,
    )
    return await hub.process_event(event)


@router.post("/ingest/sensor")
async def ingest_sensor(
    sensor_id: str = Body(..., embed=True),
    value: Any = Body(..., embed=True),
    metadata: Optional[Dict[str, Any]] = Body(None, embed=True),
    user=Depends(get_current_user)):
    hub = get_perception_hub()
    hub.ingest_sensor(sensor_id, value, metadata)
    return {"status": "queued", "sensor_id": sensor_id}


@router.post("/observe", response_model=List[PerceptionOutput])
async def observe_and_process(user=Depends(get_current_user)):
    hub = get_perception_hub()
    return await hub.observe_and_process()


@router.get("/status")
async def get_perception_status(user=Depends(get_current_user)):
    hub = get_perception_hub()
    return hub.get_status()


@router.post("/observers/{name}/toggle")
async def toggle_observer(name: str, enabled: bool = Body(..., embed=True),
    user=Depends(get_current_user)):
    hub = get_perception_hub()
    observer = hub._observers.get(name)
    if not observer:
        raise HTTPException(status_code=404, detail=f"Observer '{name}' not found")
    observer.enabled = enabled
    return {"name": name, "enabled": enabled}


@router.get("/observers")
async def list_observers(user=Depends(get_current_user)):
    hub = get_perception_hub()
    return hub.get_status()['observers']
