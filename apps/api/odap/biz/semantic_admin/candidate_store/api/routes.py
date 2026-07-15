"""Candidate Store FastAPI Routes（B2 / B4 / FR-018 / FR-019 / B7 契约）。

注册前缀：/api/semantic-admin/candidates
  FR-018 (Candidate CRUD）:
    GET  /                              → CandidateService.list_candidates（过滤 + 分页）
    GET  /{id}                          → 详情：quality_report + approval_records
    PATCH /{id}                       → CandidateService.modify_candidate（HITL 修改）
    DELETE /{id}                       → 软删 status=REJECTED（L1 才能删；其他 403）
  FR-019 (批量 + 导出):
    POST /batch-delete                  → ≤50 条批量软删
    POST /export                      → ≤10000 条 JSON 导出
  B7 (USL 写回触发）:
    POST /{id}/promote-to-usl         → 仅 admin：CandidateService.promote_to_usl

模式（对齐 AGENTS.md §附录 B 路由定义规则）：
  - except HTTPException: raise（透传）
  - 错误 400/403/404/409/500 用 HTTPException
  - 路由层不写业务逻辑，全部委派 services层
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from odap.biz.semantic_admin.candidate_store.services import CandidateService
from odap.infra.security.jwt_auth import get_current_user
from odap.biz.semantic_admin.usl_manager.api.routes import verify_semantic_writer

from .schemas import (
    BatchDeleteRequest,
    BatchDeleteResponse,
    CandidateDetailResponse,
    CandidateDeleteResponse,
    CandidateDeleteResult,
    CandidateListResponse,
    CandidateModifyRequest,
    CandidateRow,
    ExportResponse,
    PromoteToUSLRequest,
    PromoteToUSLResponse,
)

# ============
# Config
# ============

router = APIRouter(
    prefix="/api/semantic-admin/candidates",
    tags=["semantic-admin-candidates"],
)

# 模块级单例
_candidate_service = CandidateService()


# ============
# Helpers
# ============

def _map_error(result: Dict[str, Any]) -> None:
    code = str(result.get("code", "UNKNOWN_ERROR"))
    msg = str(result.get("message", code))
    detail: Any = msg
    extra = {k: v for k, v in result.items()
           if k not in ("status", "code", "message")}
    if extra:
        detail = {"message": msg, **extra}
    if code.endswith("_400"):
        raise HTTPException(status_code=400, detail=detail)
    if code.endswith("_403"):
        raise HTTPException(status_code=403, detail=detail)
    if code.endswith("_404"):
        raise HTTPException(status_code=404, detail=detail)
    if code.endswith("_409"):
        raise HTTPException(status_code=409, detail=detail)
    if code.endswith("_413"):
        raise HTTPException(status_code=413, detail=detail)
    raise HTTPException(status_code=500, detail=detail)


def _user_actor(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("sub") or user.get("username") or "system")
    return "system"


# ======================================================================
# FR-018: GET /candidates（List +分页过滤
# ======================================================================

@router.get("", response_model=CandidateListResponse)
async def list_candidates(
    workspace_id: Optional[str] = Query(default=None),
    scenario_id: Optional[str] = Query(default=None),
    domain_id: Optional[str] = Query(default=None),
    pipeline_run_id: Optional[str] = Query(default=None),
    level: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    candidate_type: Optional[str] = Query(default=None),
    canonical_q: Optional[str] = Query(default=None, description="按 canonical 模糊搜索"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    _user: Any = Depends(get_current_user),
) -> CandidateListResponse:
    try:
        result = _candidate_service.list_candidates(
            workspace_id=workspace_id,
            scenario_id=scenario_id,
            domain_id=domain_id,
            pipeline_run_id=pipeline_run_id,
            level=level,
            status=status,
            candidate_type=candidate_type,
            canonical_q=canonical_q,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)

    # list_candidates 支持两种返回：dict (items+total) 或 tuple (items,total)
    if isinstance(result, tuple):
        items_raw, total = result
    elif isinstance(result, dict):
        items_raw = list(result.get("items") or [])
        total = int(result.get("total") or len(items_raw))
    else:
        items_raw, total = [], 0
    items: list[CandidateRow] = []
    for c in items_raw:
        if isinstance(c, dict):
            items.append(CandidateRow(**{k: c.get(k, "") for k in CandidateRow.model_fields}))
    return CandidateListResponse(items=items, total=total, page=page, page_size=page_size)


# ======================================================================
# FR-018: GET /candidates/{id}（详情含 report + 审批记录）
# ======================================================================

@router.get("/{candidate_id}", response_model=CandidateDetailResponse)
async def get_candidate_detail(
    candidate_id: str,
    _user: Any = Depends(get_current_user),
) -> CandidateDetailResponse:
    try:
        result = _candidate_service.get_candidate(candidate_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    if not isinstance(result, dict) or "id" not in result:
        raise HTTPException(status_code=500, detail="候选详情格式化失败")
    # 附加 approval_records 流水（若 storage 提供）
    try:
        storage = _candidate_service.storage
        lister = getattr(storage, "list_approval_records", None)
        if lister is not None:
            recs_raw = lister(candidate_id=candidate_id, page=1, page_size=50)
            if isinstance(recs_raw, tuple):
                recs = recs_raw[0]
            elif isinstance(recs_raw, dict):
                recs = recs_raw.get("items") or []
            else:
                recs = recs_raw if isinstance(recs_raw, list) else []
        else:
            recs = []
    except Exception:
        recs = []
    merged = dict(result)
    merged["approval_records"] = recs if isinstance(recs, list) else []
    try:
        return CandidateDetailResponse(**merged)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"候选详情格式化失败: {e}")


# ======================================================================
# FR-018: PATCH /candidates/{id}（Modify）
# ======================================================================

@router.patch("/{candidate_id}", response_model=CandidateDetailResponse)
async def modify_candidate(
    candidate_id: str,
    body: CandidateModifyRequest,
    _user: Any = Depends(verify_semantic_writer),
) -> CandidateDetailResponse:
    try:
        patch = body.model_dump(exclude_unset=True)
        actor = _user_actor(_user)
        result = _candidate_service.modify_candidate(
            candidate_id, patch=patch, editor_id=actor,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    if not isinstance(result, dict) or "id" not in result:
        raise HTTPException(status_code=500, detail="修改结果为空")
    try:
        return CandidateDetailResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修改返回格式化失败: {e}")


# ======================================================================
# FR-018: DELETE /candidates/{id}（软删）
# ======================================================================

@router.delete("/{candidate_id}", response_model=CandidateDeleteResponse)
async def soft_delete_candidate(
    candidate_id: str,
    _user: Any = Depends(verify_semantic_writer),
) -> CandidateDeleteResponse:
    try:
        # 先取详情 level：仅 L1 或未分级的老数据允许软删；L2~L6 需走审批而非删
        cand = _candidate_service.storage.get_candidate(candidate_id)
        if cand is None:
            raise HTTPException(status_code=404, detail=f"候选 {candidate_id} 不存在")
        level = str(cand.get("level") or cand.get("candidate_type") or "UNSET").strip()
        forbidden_prefixes = ("L2", "L3", "L4", "L5", "L6")
        if level.startswith(forbidden_prefixes):
            raise HTTPException(
                status_code=403,
                detail=f"仅 L1 或未分级候选允许软删（当前 level={level}）。L2+ 候选须通过审批流处理",
            )
        actor = _user_actor(_user)
        # 软删：update_candidate_status REJECTED
        ok = _candidate_service.storage.update_candidate_status(candidate_id, "REJECTED")
        deleted = bool(ok)
        # 审计日志
        try:
            _candidate_service.storage.append_audit_log(
                action="candidate_soft_deleted",
                actor=actor, candidate_id=candidate_id,
                payload={"method": "soft_delete_rejected_via_delete_http"},
            )
        except Exception:
            pass
        return CandidateDeleteResponse(
            id=candidate_id,
            deleted=deleted,
            result=CandidateDeleteResult.SOFT_DELETED if deleted else CandidateDeleteResult.SKIPPED_NOT_FOUND,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ======================================================================
# FR-019: POST /candidates/batch-delete
# ======================================================================

@router.post("/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete(
    body: BatchDeleteRequest,
    _user: Any = Depends(verify_semantic_writer),
) -> BatchDeleteResponse:
    try:
        actor = _user_actor(_user)
        result = _candidate_service.batch_delete_candidates(
            body.candidate_ids, actor=actor,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="批量删除返回为空")
    try:
        return BatchDeleteResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量删除格式化失败: {e}")


# ======================================================================
# FR-019: POST /candidates/export（JSON 导出≤10000 条）
# ======================================================================

@router.post("/export", response_model=ExportResponse)
async def export_candidates(
    workspace_id: Optional[str] = Query(default=None),
    scenario_id: Optional[str] = Query(default=None),
    domain_id: Optional[str] = Query(default=None),
    pipeline_run_id: Optional[str] = Query(default=None),
    level: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    candidate_type: Optional[str] = Query(default=None),
    canonical_q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10000, ge=1, le=10000),
    _user: Any = Depends(get_current_user),
) -> ExportResponse:
    try:
        result = _candidate_service.export_candidates(
            workspace_id=workspace_id,
            scenario_id=scenario_id,
            domain_id=domain_id,
            pipeline_run_id=pipeline_run_id,
            level=level,
            status=status,
            candidate_type=candidate_type,
            canonical_q=canonical_q,
            page=page,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="导出返回为空")
    try:
        return ExportResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出格式化失败: {e}")


# ======================================================================
# B7: POST /candidates/{id}/promote-to-usl（仅 admin）
# ======================================================================

@router.post("/{candidate_id}/promote-to-usl", response_model=PromoteToUSLResponse)
async def promote_to_usl(
    candidate_id: str,
    body: PromoteToUSLRequest,
    _user: Any = Depends(verify_semantic_writer),
) -> PromoteToUSLResponse:
    try:
        admin_id = body.admin_id if body.admin_id and body.admin_id != "system" else _user_actor(_user)
        result = _candidate_service.promote_to_usl(
            candidate_id,
            admin_id=admin_id,
            force_overwrite=body.force_overwrite,
            parent_term_id=body.parent_term_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="promote_to_usl 返回为空")
    try:
        return PromoteToUSLResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"promote_to_usl 格式化失败: {e}")


__all__ = ["router"]
