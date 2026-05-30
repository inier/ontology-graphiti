from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from .schemas import (
    CreateTeamSessionRequest, RunPlanningRequest, RunOntologyRequest,
    RunExecutionRequest, ApproveStepRequest,
)
from ..services import get_team_agent_service

router = APIRouter(prefix="/api/ontology/team-agent", tags=["ontology-team-agent"])


@router.post("/sessions", response_model=dict)
async def create_session(request: CreateTeamSessionRequest):
    try:
        service = get_team_agent_service()
        return service.create_session(
            name=request.name, requirement=request.requirement,
            description=request.description,
            scenario_id=request.scenario_id, workspace_id=request.workspace_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=dict)
async def list_sessions(
    status: Optional[str] = Query(None),
    scenario_id: Optional[str] = Query(None),
):
    try:
        service = get_team_agent_service()
        return service.list_sessions(status=status, scenario_id=scenario_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=dict)
async def get_session(session_id: str):
    try:
        service = get_team_agent_service()
        result = service.get_session(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/planning", response_model=dict)
async def run_planning(session_id: str, request: RunPlanningRequest = None):
    try:
        service = get_team_agent_service()
        result = service.run_planning(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/ontology", response_model=dict)
async def run_ontology(session_id: str, request: RunOntologyRequest = None):
    try:
        service = get_team_agent_service()
        result = service.run_ontology_modeling(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/execution", response_model=dict)
async def run_execution(session_id: str, request: RunExecutionRequest = None):
    try:
        service = get_team_agent_service()
        result = service.run_execution(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/full-pipeline", response_model=dict)
async def run_full_pipeline(session_id: str):
    try:
        service = get_team_agent_service()
        result = service.run_full_pipeline(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/approve", response_model=dict)
async def approve_step(session_id: str, request: ApproveStepRequest):
    try:
        service = get_team_agent_service()
        result = service.approve_step(session_id, request.step, request.comment)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/reject", response_model=dict)
async def reject_step(session_id: str, request: ApproveStepRequest):
    try:
        service = get_team_agent_service()
        result = service.reject_step(session_id, request.step, request.comment)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
