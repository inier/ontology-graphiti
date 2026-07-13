"""Approval Workflow FastAPI Routes（C3 + C4 契约，4 动作 + list）。

注册前缀：/api/semantic-admin/approval
  C3 GET    /tasks                                         → ApprovalService.list_tasks
  C4 POST   /tasks/{task_id}/audit                         → ApprovalService.action_audit
  C4 POST   /tasks/{task_id}/modify                        → ApprovalService.action_modify
  C4 POST   /tasks/{task_id}/reject                        → ApprovalService.action_reject
  C4 POST   /tasks/{task_id}/final-approve                 → ApprovalService.action_final_approve（admin only）

路由规则（AGENTS.md §附录 B）：
  - except HTTPException: raise（透传已构造）
  - services 返回 {status:error,code,message} → 按 code 后缀映射 HTTP 状态码
  - audit/modify/reject 走 verify_semantic_writer（schema_auditor+ 权限下界，ws_role=reviewer）
  - final-approve 走 verify_semantic_admin_only（admin 全局 或 ws_role=super_admin）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from odap.biz.semantic_admin.usl_manager.api.routes import (
    verify_semantic_admin_only,
    verify_semantic_writer,
)
from odap.biz.semantic_admin.approval_workflow.services import ApprovalService
from odap.infra.security.jwt_auth import get_current_user

from .schemas import (
    ApprovalListResponse,
    AuditRequest,
    FinalApproveRequest,
    ModifyRequest,
    RejectRequest,
    ReviewResponse,
    TaskResponse,
)

router = APIRouter(prefix="/api/semantic-admin/approval", tags=["semantic-admin-approval"])
_approval_service = ApprovalService()


def _actor(user: Any, fallback: str = "system") -> str:
    if isinstance(user, dict):
        return str(user.get("sub") or user.get("username") or fallback)
    return fallback


def _map_to_http(result: Dict[str, Any]) -> None:
    code = str(result.get("code", "UNKNOWN_ERROR"))
    msg = str(result.get("message", code))
    detail: Any = msg
    if "missing_ids" in result:
        detail = {"message": msg, "missing_ids": result["missing_ids"]}
    if code.endswith("_400"):
        raise HTTPException(status_code=400, detail=detail)
    if code.endswith("_404"):
        raise HTTPException(status_code=404, detail=detail)
    if code.endswith("_409"):
        raise HTTPException(status_code=409, detail=detail)
    if code.endswith("_413"):
        raise HTTPException(status_code=413, detail=detail)
    if code.endswith("_403"):
        raise HTTPException(status_code=403, detail=detail)
    raise HTTPException(status_code=500, detail=detail)


# ======================================================================
# C3 GET /approval/tasks — 待办列表（虚拟task，基于 candidate 状态聚合）
# ======================================================================

@router.get("/tasks", response_model=ApprovalListResponse)
async def list_approval_tasks(
    assigned_role: Optional[str] = Query(
        default=None,
        description="按角色过滤：schema_auditor（L1 待办） / admin（L2 待办）",
    ),
    status: Optional[List[str]] = Query(
        default=None,
        description="按 candidate 状态过滤：PENDING_REVIEW / ADMIN_PENDING / AUDITOR_APPROVED",
    ),
    assignee_user_id: Optional[str] = Query(default=None),
    domain_id: Optional[str] = Query(default=None),
    order_by: str = Query(
        default="created_at",
        description="排序：created_at 或 priority",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _user: Any = Depends(get_current_user),
) -> ApprovalListResponse:
    try:
        result = _approval_service.list_tasks(
            assigned_role=assigned_role,
            status=status,
            assignee_user_id=assignee_user_id,
            domain_id=domain_id,
            order_by=order_by,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_to_http(result)
    try:
        return ApprovalListResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"响应格式化失败: {e}")


# ======================================================================
# C4-1 POST /approval/tasks/{task_id}/audit — schema_auditor L1 审核
# ======================================================================

@router.post("/tasks/{task_id}/audit", response_model=TaskResponse)
async def action_audit(
    task_id: str,
    body: AuditRequest,
    _user: Any = Depends(verify_semantic_writer),
) -> TaskResponse:
    try:
        result = _approval_service.action_audit(
            task_id=task_id,
            approver_id=_actor(_user),
            comment=body.comment,
            decisions=body.decisions,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_to_http(result)
    try:
        return TaskResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"响应格式化失败: {e}")


# ======================================================================
# C4-2 POST /approval/tasks/{task_id}/modify — schema_auditor 修改候选
# ======================================================================

@router.post("/tasks/{task_id}/modify", response_model=TaskResponse)
async def action_modify(
    task_id: str,
    body: ModifyRequest,
    _user: Any = Depends(verify_semantic_writer),
) -> TaskResponse:
    try:
        result = _approval_service.action_modify(
            task_id=task_id,
            approver_id=_actor(_user),
            candidate_patch=body.candidate_patch or {},
            editor_comment=body.editor_comment,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_to_http(result)
    try:
        return TaskResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"响应格式化失败: {e}")


# ======================================================================
# C4-3 POST /approval/tasks/{task_id}/reject — schema_auditor 驳回
# ======================================================================

@router.post("/tasks/{task_id}/reject", response_model=TaskResponse)
async def action_reject(
    task_id: str,
    body: RejectRequest,
    _user: Any = Depends(verify_semantic_writer),
) -> TaskResponse:
    try:
        result = _approval_service.action_reject(
            task_id=task_id,
            approver_id=_actor(_user),
            reason=body.reason,
            close_task=body.close_task,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_to_http(result)
    try:
        return TaskResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"响应格式化失败: {e}")


# ======================================================================
# C4-4 POST /approval/tasks/{task_id}/final-approve — admin L2 终审 + 写回
# ======================================================================

@router.post("/tasks/{task_id}/final-approve", response_model=TaskResponse)
async def action_final_approve(
    task_id: str,
    body: FinalApproveRequest,
    _user: Any = Depends(verify_semantic_admin_only),
) -> TaskResponse:
    """admin 终审：通过后默认 auto_promote=True 写入 USL（对应契约 B7 promote-to-usl）。"""
    try:
        result = _approval_service.action_final_approve(
            task_id=task_id,
            approver_id=_actor(_user),
            comment=body.comment,
            auto_promote=body.auto_promote,
            writeback_now=body.writeback_now,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_to_http(result)
    try:
        return TaskResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"响应格式化失败: {e}")


__all__ = ["router"]
