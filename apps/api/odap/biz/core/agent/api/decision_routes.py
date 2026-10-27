"""Agent 决策链端点（ReAct 步骤留痕）

隔离收口（ADR-091 §6 第 13-16 条 / PRD G6）：
- 全部端点不接受 workspace 入参，`workspace_id` 只由后端从 JWT 声明解析
- 声明缺失 -> 422（fail-closed）
- 跨空间命中 -> 404（与"不存在"不可区分，不泄漏存在性）
- **不接受"前端补传 workspace"作为修复**：那只是把"空 = 全量"换成"伪造 = 越权"
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from odap.infra.security.jwt_auth import get_current_user
from odap.infra.security.workspace_access import get_current_workspace

from odap.biz.core.agent.models.decision_chain import DecisionPhase
from odap.biz.core.agent.services.decision_service import DecisionScopeError, DecisionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent/decisions", tags=["agent-decisions"])

decision_service = DecisionService()

_NOT_FOUND = "决策不存在或不属于当前工作空间"


def _scope_error(exc: Exception) -> HTTPException:
    """跨空间与不存在同一响应（纵深防御，不给出存在性信号）。"""
    logger.warning("agent 决策跨空间访问被拒: %s", exc)
    return HTTPException(status_code=404, detail=_NOT_FOUND)


@router.get("/{decision_id}")
async def get_decision(
    decision_id: str,
    workspace_id: str = Depends(get_current_workspace),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """读取单条决策（含空间归属校验）。"""
    try:
        return decision_service.get_decision(decision_id, workspace_id)
    except DecisionScopeError as exc:
        raise _scope_error(exc)


@router.get("/{decision_id}/chain")
async def get_decision_chain(
    decision_id: str,
    workspace_id: str = Depends(get_current_workspace),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """读取决策链与 ReAct 步骤（含空间归属校验）。"""
    try:
        return decision_service.get_decision_chain(decision_id, workspace_id)
    except DecisionScopeError as exc:
        raise _scope_error(exc)


@router.get("")
async def list_decisions(
    page: int = Query(1, ge=1, le=100),
    page_size: int = Query(10, ge=1, le=100),
    workspace_id: str = Depends(get_current_workspace),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """空间内决策列表（读侧权威入口为 `GET /api/decisions`，此处仅保留缓冲视图）。"""
    return decision_service.list_decisions(workspace_id, page=page, page_size=page_size)


@router.post("")
async def create_decision(
    task_id: str = "",
    reasoning: str = "",
    workspace_id: str = Depends(get_current_workspace),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """建立决策链（`decision_id` 由服务端生成，空间取 JWT 声明）。"""
    return decision_service.create_decision(
        workspace_id=workspace_id, task_id=task_id, reasoning=reasoning
    )


@router.post("/{decision_id}/steps")
async def record_decision_step(
    decision_id: str,
    phase: str,
    description: str = "",
    workspace_id: str = Depends(get_current_workspace),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """追加 ReAct 步骤（Write 前校验归属，跨空间 404）。"""
    try:
        return decision_service.record_step(
            decision_id=decision_id,
            phase=DecisionPhase(phase),
            description=description,
            workspace_id=workspace_id,
        )
    except DecisionScopeError as exc:
        raise _scope_error(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
