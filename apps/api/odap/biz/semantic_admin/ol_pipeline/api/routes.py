"""OL Pipeline + Candidates FastAPI Routes（Iter 2 6层流水线 + HITL 候选审批）。

路由总前缀: /api/semantic-admin（与 usl_manager 的 /api/semantic-admin/usl 平级）

子路由组：
  POST /pipeline/runs                → 创建 Pipeline Run（若 text/extra_docs 传入则立即执行
  GET  /pipeline/runs                → 分页列出 Pipeline Runs
  GET  /pipeline/runs/{run_id}       → 获取单个 Run 元数据
  POST /pipeline/runs/{run_id}/run   → 对已创建的 Run 再次执行（可传入 text 覆盖

  GET  /candidates                   → 分页列出候选（支持 status/domain/semantic_type/confidence 过滤
  GET  /candidates/{cand_id}         → 候选详情（含质量报告合并）
  POST /candidates/{cand_id}/approve → 审批通过（HITL
  POST /candidates/{cand_id}/reject  → 审批驳回（HITL
  DELETE /candidates/{cand_id}       → 管理员清理（仅 admin

  GET  /approval-tasks               → 分页列出审批任务（status/level/condidate 过滤）
  GET  /audit-logs                   → 全链路审计（run/candidate/action 过滤）

权限约定：
  - GET 类：登录即可读（Depends(get_current_user)）
  - POST/PUT/DELETE 写类：verify_semantic_writer（3 全局角色 + 5 ws_role，与 usl_manager 统一）
  - DELETE candidates：仅 admin（verify_semantic_admin_only）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status

from odap.infra.security.jwt_auth import get_current_user
# 复用 USL 的权限函数（保证整个 semantic_admin 权限一致）
from odap.biz.semantic_admin.usl_manager.api.routes import (
    verify_semantic_writer,
    verify_semantic_admin_only,
)

from typing import Any as _Any, Dict as _Dict

from ..services import PipelineService as _OLPipelineService
from odap.biz.semantic_admin.candidate_store.services import CandidateService as _CandSvc
from .schemas import (
    ApprovalTaskListResponse,
    AuditLogListResponse,
    CandidateListResponse,
    CandidatePatchRequest,
    CandidatePatchResponse,
    CandidateResponse,
    CreatePipelineRunRequest,
    DeleteResponse,
    ApproveCandidateRequest,
    ExecuteAllRequest,
    AdvanceStepRequest,
    PipelineRunListResponse,
    PipelineRunResponse,
    PromoteToUslResponse,
    RejectCandidateRequest,
)


# 兼容别名：保持原有模块级单例命名不变
PipelineService = _OLPipelineService
CandidateService = _CandSvc


def _map_error(result: _Dict[str, _Any]) -> None:
    """services 返回 {status:'error', code:'XXX_4xx', message:'...'} 时翻译为 HTTPException。"""
    code = str(result.get("code", "UNKNOWN_ERROR"))
    msg = str(result.get("message", code))
    detail: _Any = msg
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


# =========================================================================
# 模块级单例（与 usl_manager 一致的实例化模式）
# =========================================================================
pipeline_service = PipelineService()
candidate_service = CandidateService()


router = APIRouter(prefix="/api/semantic-admin", tags=["semantic-admin-pipeline"])


# =========================================================================
# 1. Pipeline Runs
# =========================================================================


@router.post("/pipeline/runs", response_model=PipelineRunResponse)
async def create_pipeline_run(
    request: CreatePipelineRunRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """创建 Pipeline Run，若传入 text/extra_docs 则同步执行全流程。"""
    try:
        if request.text or request.extra_docs:
            result = pipeline_service.run_pipeline(
                workspace_id=request.workspace_id,
                text=request.text,
                extra_docs=list(request.extra_docs or []),
                ontology_id=request.ontology_id,
                source_type=request.source_type,
                source_ref=request.source_ref,
                triggered_by=request.triggered_by,
                config=dict(request.config or {}),
            )
            if result.get("status") == "error":
                raise HTTPException(status_code=400, detail=result["message"])
            rid = result["pipeline_run_id"]
            got = pipeline_service.get_run(rid)
            if got.get("status") == "error":
                raise HTTPException(status_code=404, detail=got["message"])
            return got
        # 未传源文本：仅创建 Run 元数据
        result = pipeline_service.create_run(
            workspace_id=request.workspace_id,
            ontology_id=request.ontology_id,
            source_type=request.source_type,
            source_ref=request.source_ref,
            triggered_by=request.triggered_by,
            total_input_chars=len(request.text or ""),
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline/runs", response_model=PipelineRunListResponse)
async def list_pipeline_runs(
    workspace_id: Optional[str] = Query(None, description="工作空间过滤"),
    status: Optional[str] = Query(None, description="状态过滤 pending/running/succeeded/failed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    try:
        return pipeline_service.list_runs(
            workspace_id=workspace_id, status=status,
            page=page, page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline/runs/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_run(
    run_id: str,
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    try:
        result = pipeline_service.get_run(run_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipeline/runs/{run_id}/run", response_model=PipelineRunResponse)
async def trigger_pipeline_run(
    run_id: str,
    text: Optional[str] = Body(None, description="覆盖 Run 中已有源文本"),
    extra_docs: Optional[list[str]] = Body(None),
    config: Optional[Dict[str, Any]] = Body(None),
    triggered_by: Optional[str] = Body(None),
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    """手动触发已创建的 Run（对已有 Run 再次执行）。"""
    try:
        run = pipeline_service.get_run(run_id)
        if run.get("status") == "error":
            raise HTTPException(status_code=404, detail=run["message"])
        result = pipeline_service.run_pipeline(
            workspace_id=run["workspace_id"],
            text=text,
            extra_docs=list(extra_docs or []),
            ontology_id=run.get("ontology_id"),
            source_type=run.get("source_type") or "natural_language",
            source_ref=run.get("source_ref"),
            triggered_by=triggered_by,
            config=dict(config or {}),
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return pipeline_service.get_run(result["pipeline_run_id"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# 2. Candidates（过滤/详情/审批/删除）
# =========================================================================


@router.get("/candidates", response_model=CandidateListResponse)
async def list_candidates(
    pipeline_run_id: Optional[str] = Query(None),
    domain_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="new/gated/approved/rejected/written"),
    semantic_type: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    try:
        return candidate_service.list_candidates(
            pipeline_run_id=pipeline_run_id,
            domain_id=domain_id,
            status=status,
            semantic_type=semantic_type,
            min_confidence=min_confidence,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: str,
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    try:
        result = candidate_service.get_candidate(candidate_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/candidates/{candidate_id}/approve", response_model=CandidateResponse)
async def approve_candidate(
    candidate_id: str,
    request: ApproveCandidateRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    try:
        result = candidate_service.approve(
            candidate_id,
            reviewer=request.reviewer,
            comment=request.comment,
            level=int(request.level or 1),
        )
        if result.get("status") == "error":
            raise HTTPException(
                status_code=404 if "不存在" in str(result["message"]) else 400,
                detail=result["message"],
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/candidates/{candidate_id}/reject", response_model=CandidateResponse)
async def reject_candidate(
    candidate_id: str,
    request: RejectCandidateRequest,
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
):
    try:
        result = candidate_service.reject(
            candidate_id,
            reviewer=request.reviewer,
            comment=request.comment,
            level=int(request.level or 1),
        )
        if result.get("status") == "error":
            raise HTTPException(
                status_code=404 if "不存在" in str(result["message"]) else 400,
                detail=result["message"],
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/candidates/{candidate_id}", response_model=DeleteResponse)
async def delete_candidate(
    candidate_id: str,
    _auth: Dict[str, Any] = Depends(verify_semantic_admin_only),
    _user: Dict[str, Any] = Depends(get_current_user),
):
    """删除候选（仅 admin 终审级。"""
    try:
        actor = _user.get("user_id") or "system"
        result = candidate_service.delete_candidate(candidate_id, actor=actor)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# 3. Approval Tasks + Audit Logs（只读）
# =========================================================================


@router.get("/approval-tasks", response_model=ApprovalTaskListResponse)
async def list_approval_tasks(
    status: Optional[str] = Query(None),
    candidate_id: Optional[str] = Query(None),
    level: Optional[int] = Query(None, ge=1, le=2),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    try:
        return candidate_service.list_approval_tasks(
            status=status, candidate_id=candidate_id, level=level,
            page=page, page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    candidate_id: Optional[str] = Query(None),
    pipeline_run_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    _auth: Dict[str, Any] = Depends(get_current_user),
):
    try:
        return candidate_service.list_audit_logs(
            candidate_id=candidate_id, pipeline_run_id=pipeline_run_id,
            action=action, page=page, page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# B3：advance / execute-all 路由
# =========================================================================


@router.post("/pipeline/runs/{run_id}/advance", response_model=PipelineRunResponse)
async def advance_run_step(
    run_id: str,
    body: AdvanceStepRequest,
    _user: Dict[str, Any] = Depends(get_current_user),
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
) -> PipelineRunResponse:
    """B3 POST /pipeline/runs/{run_id}/advance —— 推进 OL Pipeline 到指定层。

    body.to_layer: L1 / L2 / L3 / L4 / L5 / L6
    """
    try:
        actor_id = ""
        if isinstance(_user, dict):
            actor_id = str(_user.get("user_id") or _user.get("sub") or "")
        # 调用 OLPipelineService.advance_run（内部等价 pipeline_service.advance_run
        target_step = str(body.to_layer or "").strip().upper() or None
        result = pipeline_service.advance_run(
            run_id=run_id,
            target_step=target_step,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    try:
        return PipelineRunResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"advance 响应格式化失败: {e}")


@router.post("/pipeline/runs/{run_id}/execute-all")
async def execute_all_run(
    run_id: str,
    body: ExecuteAllRequest,
    response: Response,
    _user: Dict[str, Any] = Depends(get_current_user),
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
) -> Dict[str, Any]:
    """B3 POST /pipeline/runs/{run_id}/execute-all —— 推进 OL Pipeline 所有层 (异步 202)。"""
    try:
        actor_id = str(body.actor_id or "").strip()
        if not actor_id and isinstance(_user, dict):
            actor_id = str(_user.get("user_id") or _user.get("sub") or "")
        result = pipeline_service.execute_all(
            run_id=run_id,
            fail_fast=True,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    # 202 ACCEPTED（异步语义）
    response.status_code = status.HTTP_202_ACCEPTED
    return {
        "run_id": run_id, "status": "RUNNING", "estimated_seconds": 0}


# =========================================================================
# B5 / B7：candidates patch + promote-to-usl
# =========================================================================


@router.patch("/candidates/{candidate_id}", response_model=CandidatePatchResponse)
async def patch_candidate_endpoint(
    candidate_id: str,
    body: CandidatePatchRequest,
    _user: Dict[str, Any] = Depends(get_current_user),
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
) -> CandidatePatchResponse:
    """B5 PATCH /candidates/{candidate_id} —— 修改候选字段。"""
    try:
        editor_id = ""
        if isinstance(_user, dict):
            editor_id = str(_user.get("user_id") or _user.get("sub") or "unknown")
        # 构造 patch dict（只取非 None 的字段）
        patch_dict: Dict[str, Any] = {}
        if body.term is not None:
            patch_dict["term"] = body.term
        if body.canonical_label is not None:
            patch_dict["canonical_label"] = body.canonical_label
        if body.term_type is not None:
            patch_dict["term_type"] = body.term_type
        if body.synonyms is not None:
            patch_dict["synonyms"] = list(body.synonyms)
        if body.domain_id is not None:
            patch_dict["domain_id"] = body.domain_id
        if body.definition is not None:
            patch_dict["definition"] = body.definition
        if body.custom_attributes is not None:
            patch_dict["custom_attributes"] = dict(body.custom_attributes)
        if body.status is not None:
            patch_dict["status"] = body.status
        # 调用 CandidateService.modify_candidate（等价于 patch_candidate
        result = candidate_service.modify_candidate(
            candidate_id=candidate_id,
            patch=patch_dict,
            editor_id=editor_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    updated_fields = sorted(list(patch_dict.keys()))
    resp = CandidatePatchResponse(
        candidate_id=candidate_id,
        updated_fields=updated_fields,
    )
    return resp


@router.post("/candidates/{candidate_id}/promote-to-usl", response_model=PromoteToUslResponse)
async def promote_to_usl_endpoint(
    candidate_id: str,
    overwrite: bool = Query(default=False, description="若 USL 已存在同 term 是否覆盖"),
    actor_id: str = Query(default="", description="操作者 ID（可选，缺省从 JWT 取）"),
    _user: Dict[str, Any] = Depends(get_current_user),
    _auth: Dict[str, Any] = Depends(verify_semantic_writer),
) -> PromoteToUslResponse:
    """B7 POST /candidates/{candidate_id}/promote-to-usl —— 将候选提升写入 USL。"""
    try:
        approver_id = actor_id.strip()
        if not approver_id and isinstance(_user, dict):
            approver_id = str(_user.get("user_id") or _user.get("sub") or "system")
        result = candidate_service.promote_to_usl(
            candidate_id=candidate_id,
            admin_id=approver_id,
            force_overwrite=bool(overwrite),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if isinstance(result, dict) and result.get("status") == "error":
        _map_error(result)
    # 解析 promote_to_usl 结果 → PromoteToUslResponse
    writeback_status = ""
    conflicts: List[Dict[str, Any]] = []
    usl_term_id = result.get("usl_term_id") if isinstance(result, dict) else None
    created_new = bool(result.get("created_new") if isinstance(result, dict) else False)
    overwrote = bool(result.get("overwrote_existing") if isinstance(result, dict) else False)
    if isinstance(result, dict):
        code_in_result = str(result.get("code", "")).upper()
        if "TERM_EXISTS" in code_in_result:
            writeback_status = "TERM_EXISTS"
        elif "FAILED" in code_in_result or result.get("status") == "error":
            writeback_status = "FAILED"
        else:
            writeback_status = "WRITTEN_BACK"
        # conflicts 提取：usl_term_id存在冲突详情
        if "conflicts" in result and isinstance(result.get("conflicts"), list):
            conflicts = list(result["conflicts"])
    return PromoteToUslResponse(
        candidate_id=candidate_id,
        writeback_status=writeback_status,
        conflicts=conflicts,
        usl_term_id=usl_term_id,
        created_new=created_new,
        overwrote_existing=overwrote,
    )
