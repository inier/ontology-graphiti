from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from odap.web.api.response_models import DictResponse

from ..services.decay_scheduler import MemoryDecayScheduler, DecayConfig

router = APIRouter(prefix="/api/ontology-memory/decay", tags=["ontology-memory-decay"])


class DecayConfigRequest(BaseModel):
    default_half_life_hours: Optional[float] = None
    min_importance_threshold: Optional[float] = None
    consolidation_threshold: Optional[float] = None
    decay_check_interval_seconds: Optional[float] = None
    batch_size: Optional[int] = None


@router.post("/trigger", response_model=DictResponse)
async def trigger_decay():
    try:
        scheduler = MemoryDecayScheduler.get_instance()
        result = scheduler.run_decay_cycle()
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=DictResponse)
async def get_decay_stats():
    try:
        scheduler = MemoryDecayScheduler.get_instance()
        return scheduler.get_stats()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start", response_model=DictResponse)
async def start_scheduler():
    try:
        scheduler = MemoryDecayScheduler.get_instance()
        scheduler.start()
        return {"status": "success", "message": "Decay scheduler started"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=DictResponse)
async def stop_scheduler():
    try:
        scheduler = MemoryDecayScheduler.get_instance()
        scheduler.stop()
        return {"status": "success", "message": "Decay scheduler stopped"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config", response_model=DictResponse)
async def update_config(request: DecayConfigRequest):
    try:
        scheduler = MemoryDecayScheduler.get_instance()
        kwargs = {k: v for k, v in request.model_dump().items() if v is not None}
        if not kwargs:
            raise HTTPException(status_code=400, detail="No config values provided")
        return scheduler.update_config(**kwargs)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
