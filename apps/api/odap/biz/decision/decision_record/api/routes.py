"""决策智能 API 路由（ADR-076 §8：7 端点）

隔离规则（ADR-076 §7）：
- workspace_id 一律路由层解析（JWT 声明或 assert_workspace_access 覆盖），不信任客户端透传
- workspace_id 为空 → 422 直接拒绝
- 全部读写携带 decision_id AND workspace_id 双条件
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from odap.infra.security.jwt_auth import get_current_user
from odap.infra.middleware.exception_handler import APIError
from odap.infra.security.workspace_access import assert_workspace_access, get_current_workspace

from odap.biz.decision.decision_record.models import (
    CausalLinkType,
    DecisionChain,
    DecisionGateResult,
    DecisionImpact,
    DecisionOutcome,
    DecisionRecord,
    DecisionStatus,
    StatusOutcomePatch,
)
from odap.biz.decision.decision_record.models.status_matrix import DecisionInvariantError
from odap.biz.decision.decision_record.services import get_decision_service

logger = logging.getLogger(__name__)

decision_record_router = APIRouter(prefix="/api/decisions", tags=["决策智能"])


# ---------- 请求模型 ----------


class DecisionRecordCreate(BaseModel):
    """record_decision 请求体（ADR-076 §8）"""

    workspace_id: Optional[str] = Field(None, description="工作空间（可选，缺省取 JWT 声明）")
    context_summary: str = Field(default="", description="决策场景描述")
    constraints: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str = Field(default="", description="推理过程摘要")
    reasoning_trace: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_episode_ids: List[str] = Field(default_factory=list)
    evidence_entity_ids: List[str] = Field(default_factory=list)
    recommended_option: str = Field(default="", description="选定方案")
    alternative_options: List[str] = Field(default_factory=list)
    decision_method: str = Field(default="manual", description="决策方法")
    decision_type: str = Field(default="general", description="决策类型")
    parent_decision_id: Optional[str] = None
    root_goal_id: Optional[str] = None
    precedent_decision_ids: List[str] = Field(
        default_factory=list, description="实际采纳的先例（自动建立 PRECEDENT_FOR 留痕）"
    )
    agent_id: Optional[str] = None


class CausalLinkCreate(BaseModel):
    """add_causal_relationship 请求体（ADR-076 §4.5）"""

    to_decision_id: str = Field(description="目标决策 ID")
    link_type: CausalLinkType = Field(description="因果边类型")
    workspace_id: Optional[str] = Field(None, description="可选，缺省取 JWT 声明")


class CheckRulesRequest(BaseModel):
    """check_decision_rules 请求体（ADR-076 §4.6）"""

    action: str = Field(description="动作标识，如 decision.execute")
    resource: Dict[str, Any] = Field(description="资源描述")
    environment: Dict[str, Any] = Field(default_factory=dict)
    workspace_id: Optional[str] = Field(None, description="可选，缺省取 JWT 声明")


class OutcomeUpdate(BaseModel):
    """update_decision_outcome 请求体（ADR-076 §4.7 + ADR-091 §5.2.1）

    `status` 必填：只给 `outcome` 的写入无法校验 7/23 矩阵，等于绕开写侧守门。
    """

    status: DecisionStatus
    outcome: DecisionOutcome
    outcome_details: Dict[str, Any] = Field(default_factory=dict)
    feedback_summary: Optional[str] = None


# ---------- 端点 ----------


@decision_record_router.post("", response_model=DecisionRecord)
async def record_decision(body: DecisionRecordCreate, user=Depends(get_current_user)):
    """决策落库（一等公民节点 + 证据/因果边 + 审计 Episode）。"""
    workspace_id = assert_workspace_access(user, body.workspace_id)
    record = DecisionRecord(
        workspace_id=workspace_id,
        context_summary=body.context_summary,
        constraints=body.constraints,
        reasoning=body.reasoning,
        reasoning_trace=body.reasoning_trace,
        confidence=body.confidence,
        evidence_episode_ids=body.evidence_episode_ids,
        evidence_entity_ids=body.evidence_entity_ids,
        recommended_option=body.recommended_option,
        alternative_options=body.alternative_options,
        decision_method=body.decision_method,
        decision_type=body.decision_type,
        parent_decision_id=body.parent_decision_id,
        root_goal_id=body.root_goal_id,
        precedent_decision_ids=body.precedent_decision_ids,
        agent_id=body.agent_id or user.get("sub"),
    )
    try:
        service = get_decision_service()
        return await service.record_decision(record)
    except (APIError, DecisionInvariantError):
        raise  # 409/422 的码与信封由中间件原样透出，不得压成 422 纯字符串或 500
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("决策落库失败: %s", e)
        raise HTTPException(status_code=500, detail=f"决策落库失败: {e}")


@decision_record_router.get("/{decision_id}/chain", response_model=DecisionChain)
async def get_decision_chain(decision_id: str, workspace_id: str = Depends(get_current_workspace)):
    """因果链追溯（证据 + 上游 CAUSE 链 + 先例）。"""
    service = get_decision_service()
    chain = await service.trace_decision_chain(decision_id, workspace_id)
    if chain is None:
        raise HTTPException(status_code=404, detail="决策不存在或不属于当前工作空间")
    return chain


@decision_record_router.get("/similar", response_model=List[DecisionRecord])
async def find_similar_decisions(
    context: str = Query(..., description="当前决策场景描述"),
    top_k: int = Query(5, ge=1, le=20),
    workspace_id: str = Depends(get_current_workspace),
):
    """先例搜索（Graphiti 向量检索优先，Cypher 文本扫描降级）。"""
    service = get_decision_service()
    return await service.find_similar_decisions(workspace_id, context, top_k)


@decision_record_router.get("/{decision_id}/impact", response_model=DecisionImpact)
async def analyze_decision_impact(decision_id: str, workspace_id: str = Depends(get_current_workspace)):
    """影响分析（下游决策 + 目标变化 + 协同证据，含完整性标注）。"""
    service = get_decision_service()
    impact = await service.analyze_decision_impact(decision_id, workspace_id)
    if impact is None:
        raise HTTPException(status_code=404, detail="决策不存在或不属于当前工作空间")
    return impact


@decision_record_router.post("/{decision_id}/causal-links")
async def add_causal_link(
    decision_id: str, body: CausalLinkCreate, user=Depends(get_current_user)
):
    """显式建立因果边（同空间校验 + CAUSED_BY 环检测）。"""
    workspace_id = assert_workspace_access(user, body.workspace_id)
    service = get_decision_service()
    try:
        link = await service.add_causal_relationship(
            from_decision_id=decision_id,
            to_decision_id=body.to_decision_id,
            link_type=body.link_type,
            workspace_id=workspace_id,
        )
        return {"success": True, "link": link.model_dump(mode="json")}
    except (APIError, DecisionInvariantError):
        raise  # 409/422 的码与信封由中间件原样透出，不得压成 422 纯字符串或 500
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("因果边建立失败: %s", e)
        raise HTTPException(status_code=500, detail=f"因果边建立失败: {e}")


@decision_record_router.post("/check-rules", response_model=DecisionGateResult)
async def check_decision_rules(body: CheckRulesRequest, user=Depends(get_current_user)):
    """落库前规则门禁（Phase 1 = OPA 权限门禁前移）。"""
    workspace_id = assert_workspace_access(user, body.workspace_id)
    service = get_decision_service()
    try:
        return await service.check_decision_rules(
            workspace_id=workspace_id,
            user=user,
            action=body.action,
            resource=body.resource,
            environment=body.environment,
        )
    except (APIError, DecisionInvariantError):
        raise  # 409/422 的码与信封由中间件原样透出，不得压成 422 纯字符串或 500
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("规则门禁校验失败: %s", e)
        raise HTTPException(status_code=500, detail=f"规则门禁校验失败: {e}")


@decision_record_router.patch("/{decision_id}/outcome", response_model=DecisionRecord)
async def update_decision_outcome(
    decision_id: str, body: OutcomeUpdate, workspace_id: str = Depends(get_current_workspace)
):
    """状态与结果回填（status + outcome 同一次原子写，更新条件含双条件）。"""
    service = get_decision_service()
    patch = StatusOutcomePatch(
        status=body.status, outcome=body.outcome, details=body.outcome_details
    )
    ok = await service.update_decision_outcome(
        decision_id=decision_id,
        workspace_id=workspace_id,
        patch=patch,
        feedback_summary=body.feedback_summary,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="决策不存在或不属于当前工作空间")
    record = await service.store.get_decision(decision_id, workspace_id)
    return record
