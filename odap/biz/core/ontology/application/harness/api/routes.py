from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Optional

from .schemas import (
    CreateSessionRequest, AdvanceStageRequest, FailStageRequest,
    CreateHITLRequest, ResolveHITLRequest,
    AddAgentTaskRequest, UpdateAgentTaskRequest, UpdateContextRequest,
    CheckHITLRequest, CreateBlueprintRequest, UpdateBlueprintRequest,
    RunPlanningRequest, RunOntologyRequest, RunExecutionRequest,
    ApproveStepRequest, RejectStepRequest,
    DictResponse,
)
from ..services import get_harness_service

router = APIRouter(prefix="/api/ontology/harness", tags=["ontology-harness"])


@router.post("/sessions", response_model=DictResponse)
async def create_session(request: CreateSessionRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        return service.create_session(
            name=request.name, description=request.description,
            scenario_id=request.scenario_id, workspace_id=request.workspace_id,
            requirement=request.requirement,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=DictResponse)
async def list_sessions(
    status: Optional[str] = Query(None),
    scenario_id: Optional[str] = Query(None),
    _user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        return service.list_sessions(status=status, scenario_id=scenario_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=DictResponse)
async def get_session(session_id: str,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.get_session(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/advance", response_model=DictResponse)
async def advance_stage(session_id: str, request: AdvanceStageRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.advance_stage(session_id, stage_output=request.stage_output)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/fail", response_model=DictResponse)
async def fail_stage(session_id: str, request: FailStageRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        return service.fail_stage(session_id, request.error)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}", response_model=DictResponse)
async def delete_session(session_id: str,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.delete_session(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/hitl", response_model=DictResponse)
async def create_hitl(session_id: str, request: CreateHITLRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        return service.create_hitl_confirmation(
            session_id, request.stage, request.risk_level,
            request.title, request.description, request.affected_objects,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/hitl/resolve", response_model=DictResponse)
async def resolve_hitl(session_id: str, request: ResolveHITLRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.resolve_hitl(session_id, request.confirmation_id, request.resolution, request.resolved_by)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hitl/check", response_model=DictResponse)
async def check_hitl(request: CheckHITLRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        return service.check_hitl_required(request.operation, request.affected_types)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/tasks", response_model=DictResponse)
async def add_agent_task(session_id: str, request: AddAgentTaskRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        return service.add_agent_task(session_id, request.agent_type, request.stage, request.description, request.input_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sessions/{session_id}/tasks", response_model=DictResponse)
async def update_agent_task(session_id: str, request: UpdateAgentTaskRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        return service.update_agent_task(session_id, request.task_id, request.output_data, request.status, request.error)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sessions/{session_id}/context", response_model=DictResponse)
async def update_context(session_id: str, request: UpdateContextRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        return service.update_context(session_id, request.key, request.value)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blueprints", response_model=DictResponse)
async def create_blueprint(request: CreateBlueprintRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        return service.create_blueprint(request.name, request.description, request.session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blueprints", response_model=DictResponse)
async def list_blueprints(session_id: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        return service.list_blueprints(session_id=session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blueprints/{blueprint_id}", response_model=DictResponse)
async def get_blueprint(blueprint_id: str,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.get_blueprint(blueprint_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/blueprints/{blueprint_id}", response_model=DictResponse)
async def update_blueprint(blueprint_id: str, request: UpdateBlueprintRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.update_blueprint(blueprint_id, request.model_dump(exclude_none=True))
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/blueprints/{blueprint_id}", response_model=DictResponse)
async def delete_blueprint(blueprint_id: str,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.delete_blueprint(blueprint_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/planning", response_model=DictResponse)
async def run_planning(session_id: str, request: RunPlanningRequest = None,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.run_planning(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/ontology", response_model=DictResponse)
async def run_ontology(session_id: str, request: RunOntologyRequest = None,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.run_ontology_modeling(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/execution", response_model=DictResponse)
async def run_execution(session_id: str, request: RunExecutionRequest = None,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.run_execution(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/full-pipeline", response_model=DictResponse)
async def run_full_pipeline(session_id: str,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.run_full_pipeline(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/approve", response_model=DictResponse)
async def approve_step(session_id: str, request: ApproveStepRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.approve_step(session_id, request.stage, request.approved_by)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/reject", response_model=DictResponse)
async def reject_step(session_id: str, request: RejectStepRequest,
    user=Depends(get_current_user)):
    try:
        service = get_harness_service()
        result = service.reject_step(session_id, request.stage, request.reason)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
