from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Optional
from ..services.memory_service import OntologyMemoryService
from .schemas import (
    StoreMemoryRequest, RetrieveMemoryRequest, ConsolidateMemoriesRequest,
    DecayUpdateRequest, ForgetRequest
)

router = APIRouter(prefix="/api/ontology-memory", tags=["ontology-memory"])

memory_service = OntologyMemoryService()


@router.post("/memories")
async def store_memory(request: StoreMemoryRequest,
    user=Depends(get_current_user)):
    try:
        result = memory_service.store_memory(
            memory_type=request.memory_type.value,
            content=request.content,
            summary=request.summary,
            keywords=request.keywords,
            entities=request.entities,
            source_scenario_id=request.source_scenario_id,
            source_session_id=request.source_session_id,
            importance=request.importance,
            metadata=request.metadata
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories")
async def list_memories(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    memory_type: Optional[str] = None,
    status: Optional[str] = None,
    source_scenario_id: Optional[str] = None,
    user=Depends(get_current_user)):
    try:
        result = memory_service.list_memories(
            memory_type=memory_type,
            status=status,
            source_scenario_id=source_scenario_id,
            page=page,
            page_size=page_size
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories/{memory_id}")
async def get_memory(memory_id: str,
    user=Depends(get_current_user)):
    try:
        result = memory_service.get_memory(memory_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str,
    user=Depends(get_current_user)):
    try:
        result = memory_service.delete_memory(memory_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memories/retrieve")
async def retrieve_memories(request: RetrieveMemoryRequest,
    user=Depends(get_current_user)):
    try:
        result = memory_service.retrieve_memories(
            query=request.query,
            memory_type=request.memory_type.value if request.memory_type else None,
            top_k=request.top_k,
            scenario_id=request.scenario_id,
            method_weights=request.method_weights
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memories/consolidate")
async def consolidate_memories(request: ConsolidateMemoriesRequest,
    user=Depends(get_current_user)):
    try:
        result = memory_service.consolidate_memories(
            memory_ids=request.memory_ids,
            strategy=request.strategy
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memories/decay")
async def decay_update(request: DecayUpdateRequest,
    user=Depends(get_current_user)):
    try:
        config = {}
        if request.half_life_days is not None:
            config["half_life_days"] = request.half_life_days
        if request.min_decay_factor is not None:
            config["min_decay_factor"] = request.min_decay_factor
        if request.access_boost is not None:
            config["access_boost"] = request.access_boost
        if request.importance_weight is not None:
            config["importance_weight"] = request.importance_weight
        if request.recency_weight is not None:
            config["recency_weight"] = request.recency_weight
        if request.frequency_weight is not None:
            config["frequency_weight"] = request.frequency_weight
        result = memory_service.decay_update(config=config if config else None)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memories/forget")
async def forget_memories(request: ForgetRequest,
    user=Depends(get_current_user)):
    try:
        result = memory_service.forget_memories(
            threshold=request.threshold,
            archive=request.archive
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics(scenario_id: Optional[str] = None,
    user=Depends(get_current_user)):
    try:
        result = memory_service.get_statistics(scenario_id=scenario_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
