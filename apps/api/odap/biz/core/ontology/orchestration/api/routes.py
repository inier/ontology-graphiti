"""本体约束问答路由（F6 / F8 / F9 暴露面）。

5 个端点（SPEC-v2 §5 + AC-40~AC-42 动作闭环）：
    POST /api/v1/ontology/qa
    GET  /api/v1/ontology/qa/{trace_id}/provenance
    GET  /api/v1/ontology/qa/{trace_id}/actions
    POST /api/v1/ontology/qa/actions/{action_id}/approve
    POST /api/v1/ontology/qa/actions/{action_id}/execute

路由零业务：请求校验 → 调管线/仓储/动作服务 → 组装包络。业务错误由 ApiError 冒泡。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from odap.common import api_errors as E
from odap.common.api_errors import ApiError
from odap.common.envelope import envelope
from odap.biz.core.ontology.orchestration.actions.service import ActionService
from odap.biz.core.ontology.orchestration.api.schemas import QaActionDecision, QaRequest
from odap.biz.core.ontology.orchestration.pipeline import QaPipeline
from odap.biz.core.ontology.orchestration.repositories.trace_repo import QaTraceRepository
from odap.infra.security.jwt_auth import get_current_user

router = APIRouter(prefix="/api/v1/ontology", tags=["Ontology QA"])

_SERVICES: Dict[str, Any] = {}


def set_services(**services: Any) -> None:
    _SERVICES.update(services)


def reset_services() -> None:
    _SERVICES.clear()


def _svc(name: str, factory):
    if name not in _SERVICES:
        _SERVICES[name] = factory()
    return _SERVICES[name]


@router.post("/qa")
async def ontology_qa(body: QaRequest, user=Depends(get_current_user)):
    query = (body.query or "").strip()
    if not query:
        raise ApiError(
            E.QA_QUERY_REQUIRED, "query 不能为空：请提交要分析的自然语言问题", status_code=400,
            detail={"field": "query"},
        )
    pipeline: QaPipeline = _svc("pipeline", QaPipeline)
    answer, _provenance = await pipeline.run(
        query=query,
        user_ctx=user if isinstance(user, dict) else {},
        workspace_id=body.workspace_id or "",
        mode=body.mode.value,
        allow_actions=body.allow_actions,
    )
    return envelope(answer.model_dump(mode="json"))


@router.get("/qa/{trace_id}/provenance")
async def get_provenance(trace_id: str, _user=Depends(get_current_user)):
    repo: QaTraceRepository = _svc("trace_repo", QaTraceRepository)
    provenance: Optional[Any] = repo.get_provenance(trace_id)
    if provenance is None:
        raise ApiError(
            E.QA_TRACE_NOT_FOUND, f"溯源记录不存在：{trace_id}", status_code=404,
            detail={"trace_id": trace_id},
        )
    return envelope(provenance.model_dump(mode="json"))


# ── F9 Action / HITL（AC-40~AC-42）────────────────────────────────────────────

@router.get("/qa/{trace_id}/actions")
async def list_actions(trace_id: str, _user=Depends(get_current_user)):
    """列出该次问答派生出的动作（含 HITL 状态）。"""
    service: ActionService = _svc("actions", ActionService)
    return envelope({"trace_id": trace_id, "actions": service.list(trace_id)})


@router.post("/qa/actions/{action_id}/approve")
async def decide_action(action_id: str, body: QaActionDecision,
                        user=Depends(get_current_user)):
    """HITL 审批：批准 / 驳回高风险动作（低风险动作会 409 拒绝，无需审批）。"""
    service: ActionService = _svc("actions", ActionService)
    user_ctx = user if isinstance(user, dict) else {}
    action = service.decide(action_id, approved=body.approved, user_ctx=user_ctx)
    return envelope(action)


@router.post("/qa/actions/{action_id}/execute")
async def execute_action(action_id: str, _user=Depends(get_current_user)):
    """执行动作：低风险直接执行；高风险未 `approved` 时 409 ACTION_HITL_REQUIRED。"""
    service: ActionService = _svc("actions", ActionService)
    return envelope(service.execute(action_id))
