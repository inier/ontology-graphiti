from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import List, Optional

from .schemas import ActionRequest, ActionRecord, ActionApproval, ActionRequestStatus
from .services.action_query_service import get_action_query_service
from .executor import get_action_executor

router = APIRouter(prefix="/api/actions", tags=["action-service"])

action_query_service = get_action_query_service()


def _audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, service: str = "decision", workspace_id: str = "default"):
    """审计便捷函数"""
    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource="decision",
            user=user_id,
            service=service,
            result_status=result_status,
            result_message=result_message,
            details=details or {},
            workspace_id=workspace_id,
        )
    except Exception:
        pass


@router.post("/submit", response_model=ActionRecord)
async def submit_action(request: ActionRequest,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    executor = get_action_executor()
    try:
        record = await executor.submit_action(request)
        _audit("decision_submit_action", _uid, "success", details={"action_type": request.action_type if hasattr(request, 'action_type') else ""})
        return record
    except ValueError as e:
        _audit("decision_submit_action_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        _audit("decision_submit_action_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{record_id}/approve", response_model=ActionRecord)
async def approve_action(record_id: str, approval: ActionApproval,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    executor = get_action_executor()
    try:
        record = await executor.approve_and_execute(
            record_id, approver=approval.approver, comment=approval.comment
        )
        _audit("decision_approve_action", _uid, "success", details={"record_id": record_id})
        return record
    except ValueError as e:
        _audit("decision_approve_action_failed", _uid, "failure", str(e), details={"record_id": record_id})
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        _audit("decision_approve_action_failed", _uid, "failure", str(e), details={"record_id": record_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records", response_model=List[ActionRecord])
async def list_action_records(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        return action_query_service.list_records(status=status, limit=limit, offset=offset)
    except HTTPException:
        raise
    except Exception as e:
        _audit("decision_list_records_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records/{record_id}", response_model=ActionRecord)
async def get_action_record(record_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        record = action_query_service.get_record(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="动作记录不存在")
        return record
    except HTTPException:
        raise
    except Exception as e:
        _audit("decision_get_record_failed", _uid, "failure", str(e), details={"record_id": record_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/target/{target_object_id}", response_model=List[ActionRecord])
async def list_actions_by_target(target_object_id: str, limit: int = Query(20),
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        return action_query_service.list_by_target(target_object_id, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        _audit("decision_list_by_target_failed", _uid, "failure", str(e), details={"target_object_id": target_object_id})
        raise HTTPException(status_code=500, detail=str(e))
