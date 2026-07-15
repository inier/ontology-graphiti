"""USL Writeback FastAPI Routes（I4T8 契约）。

注册总前缀：/api/semantic-admin（与整个 semantic_admin 套件统一挂载）

路由组：
  POST /writeback/candidates/{candidate_id}   — 手动触发写回 → WritebackService.trigger_manual_writeback
  GET  /writeback/status/{candidate_id}       — 查询写回状态 → WritebackService.get_writeback_status

权限约定：
  - GET 类：登录即可读（Depends(get_current_user)）
  - POST 类写操作：verify_semantic_writer（整个 semantic_admin 套件统一校验）
  - 错误：HTTPException（status=500 兜底）；服务层 code 结尾为 _404/_400/_409 时映射为相应状态码
  - 严格遵循「except HTTPException: raise」透传规则（AGENTS.md §B）
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status

from odap.biz.semantic_admin.usl_manager.api.routes import verify_semantic_writer
from odap.infra.security.jwt_auth import get_current_user

from ..services import WritebackService
from .schemas import (
    WritebackStatusResponse,
    WritebackTriggerRequest,
    WritebackTriggerResponse,
)


# ======================================================================
# 单例 + 路由前缀（统一挂 /api/semantic-admin）
# ======================================================================

_writeback_service = WritebackService()

router = APIRouter(
    prefix="/api/semantic-admin/writeback",
    tags=["semantic-admin-writeback"],
)


# ======================================================================
# 工具：服务层错误码 → HTTP 状态码
# ======================================================================

def _map_error(result: dict) -> None:
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
    raise HTTPException(status_code=500, detail=detail)


# ======================================================================
# I4T8 - POST /writeback/candidates/{candidate_id}
# ======================================================================

@router.post(
    "/candidates/{candidate_id}",
    response_model=WritebackTriggerResponse,
)
async def trigger_writeback_manual(
    candidate_id: str,
    body: WritebackTriggerRequest = Body(
        default_factory=WritebackTriggerRequest,
        description="手动触发写回的可选参数，缺省用 user_manual",
    ),
    response: Response = Response(),
    _user: Any = Depends(verify_semantic_writer),
) -> WritebackTriggerResponse:
    """I4T8：管理员手动触发单个 Candidate 的 USL 写回（幂等）。"""
    try:
        actor = body.executed_by
        if not actor and isinstance(_user, dict):
            actor = _user.get("sub") or "user_manual"
        if not actor:
            actor = "user_manual"
        result = _writeback_service.trigger_manual_writeback(
            candidate_id,
            executed_by=actor,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"手动写回执行失败: {e}")

    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    try:
        # 已 written_back / 降级伪成功都是 200；幂等也 200（无 side effect）
        response.status_code = status.HTTP_200_OK
        return WritebackTriggerResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"响应格式化失败: {e}")


# ======================================================================
# I4T8 - GET /writeback/status/{candidate_id}
# ======================================================================

@router.get(
    "/status/{candidate_id}",
    response_model=WritebackStatusResponse,
)
async def get_writeback_status_endpoint(
    candidate_id: str,
    _user: Any = Depends(get_current_user),
) -> WritebackStatusResponse:
    """I4T8：查询单个 Candidate 的写回状态（in_pipeline / approved_pending / written_back / rejected）。"""
    try:
        result = _writeback_service.get_writeback_status(candidate_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写回状态查询失败: {e}")

    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    try:
        return WritebackStatusResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"状态格式化失败: {e}")


__all__ = ["router"]
