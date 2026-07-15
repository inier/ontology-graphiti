from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Optional

from .runtime_schemas import StartExecutionRequest, DictResponse
from ..services.blueprint_runtime import BlueprintRuntimeEngine

router = APIRouter(prefix="/api/ontology/blueprints/executions", tags=["blueprint-runtime"])
engine = BlueprintRuntimeEngine.get_instance()


@router.post("", response_model=DictResponse)
async def start_execution(request: StartExecutionRequest,
    user=Depends(get_current_user)):
    try:
        result = engine.start_execution(
            execution_id=request.execution_id,
            blueprint_id=request.blueprint_id,
            metadata=request.metadata,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{execution_id}/pause", response_model=DictResponse)
async def pause_execution(execution_id: str,
    user=Depends(get_current_user)):
    try:
        result = engine.pause_execution(execution_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{execution_id}/resume", response_model=DictResponse)
async def resume_execution(execution_id: str,
    user=Depends(get_current_user)):
    try:
        result = engine.resume_execution(execution_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{execution_id}/cancel", response_model=DictResponse)
async def cancel_execution(execution_id: str,
    user=Depends(get_current_user)):
    try:
        result = engine.cancel_execution(execution_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{execution_id}", response_model=DictResponse)
async def get_execution(execution_id: str,
    user=Depends(get_current_user)):
    try:
        result = engine.get_execution(execution_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=DictResponse)
async def list_executions(
    blueprint_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    try:
        return engine.list_executions(blueprint_id=blueprint_id, status=status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
