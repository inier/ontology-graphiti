from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional

from odap.biz.core.agent.services.decision_service import DecisionService
from odap.biz.core.agent.models.decision_chain import DecisionPhase

router = APIRouter(prefix="/api/agent/decisions", tags=["agent-decisions"])

decision_service = DecisionService()


@router.get("/{decision_id}")
async def get_decision(decision_id: str) -> Dict[str, Any]:
    try:
        result = decision_service.get_decision(decision_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{decision_id}/chain")
async def get_decision_chain(decision_id: str) -> Dict[str, Any]:
    try:
        result = decision_service.get_decision_chain(decision_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_decisions(
    workspace_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> Dict[str, Any]:
    try:
        return decision_service.list_decisions(workspace_id=workspace_id, page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_decision(
    task_id: str = "",
    workspace_id: Optional[str] = None,
    reasoning: str = "",
) -> Dict[str, Any]:
    try:
        return decision_service.create_decision(
            task_id=task_id,
            workspace_id=workspace_id,
            reasoning=reasoning,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{decision_id}/steps")
async def record_decision_step(
    decision_id: str,
    phase: str,
    description: str = "",
) -> Dict[str, Any]:
    try:
        result = decision_service.record_step(
            decision_id=decision_id,
            phase=DecisionPhase(phase),
            description=description,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
