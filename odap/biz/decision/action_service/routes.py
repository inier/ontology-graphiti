from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import List, Optional

from .schemas import ActionRequest, ActionRecord, ActionApproval, ActionRequestStatus
from .services.action_query_service import get_action_query_service
from .executor import get_action_executor

router = APIRouter(prefix="/api/actions", tags=["action-service"])

action_query_service = get_action_query_service()


@router.post("/submit", response_model=ActionRecord)
async def submit_action(request: ActionRequest,
    user=Depends(get_current_user)):
    executor = get_action_executor()
    try:
        record = await executor.submit_action(request)
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{record_id}/approve", response_model=ActionRecord)
async def approve_action(record_id: str, approval: ActionApproval,
    user=Depends(get_current_user)):
    executor = get_action_executor()
    try:
        record = await executor.approve_and_execute(
            record_id, approver=approval.approver, comment=approval.comment
        )
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/records", response_model=List[ActionRecord])
async def list_action_records(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user)):
    return action_query_service.list_records(status=status, limit=limit, offset=offset)


@router.get("/records/{record_id}", response_model=ActionRecord)
async def get_action_record(record_id: str,
    user=Depends(get_current_user)):
    record = action_query_service.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="动作记录不存在")
    return record


@router.get("/target/{target_object_id}", response_model=List[ActionRecord])
async def list_actions_by_target(target_object_id: str, limit: int = Query(20),
    user=Depends(get_current_user)):
    return action_query_service.list_by_target(target_object_id, limit=limit)
