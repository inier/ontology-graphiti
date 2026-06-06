"""OntoFlow Goal - Pydantic 请求/响应模型 (T426)"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateGoalRequest(BaseModel):
    """创建 Goal 请求"""
    title: str
    description: str = ""
    business_objective: str
    workspace_id: str
    created_by: str
    parent_goal_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    auto_rationale: bool = True


class UpdateGoalRequest(BaseModel):
    """更新 Goal 请求（所有字段可选）"""
    title: Optional[str] = None
    description: Optional[str] = None
    business_objective: Optional[str] = None
    rationale: Optional[str] = None
    parent_goal_id: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class GoalResponse(BaseModel):
    """Goal 响应"""
    id: str
    title: str
    description: str = ""
    business_objective: str
    rationale: Optional[str] = None
    status: str = "proposed"
    parent_goal_id: Optional[str] = None
    workspace_id: str
    created_by: str
    created_at: str
    updated_at: str
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ListGoalsResponse(BaseModel):
    """列出 Goal 响应"""
    goals: List[GoalResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    count: int = 0


class StatusTransitionRequest(BaseModel):
    """状态机转换请求"""
    new_status: str


class ProposeChangeRequest(BaseModel):
    """创建 ChangeProposal 请求"""
    title: str
    description: str = ""
    changes: List[Dict[str, Any]] = Field(default_factory=list)
    proposed_by: str
    estimated_benefit: str = ""
    estimated_cost: Optional[str] = None


class ProposalResponse(BaseModel):
    """ChangeProposal 响应"""
    id: str
    goal_id: str
    title: str
    description: str = ""
    changes: List[Dict[str, Any]] = Field(default_factory=list)
    impact_analysis_id: Optional[str] = None
    estimated_benefit: str = ""
    estimated_cost: Optional[str] = None
    status: str = "draft"
    proposed_by: str
    created_at: str
    reviewed_at: Optional[str] = None
    reviewer_notes: Optional[str] = None


class ImpactResponse(BaseModel):
    """ImpactAnalysis 响应"""
    id: str
    proposal_id: str
    affected_object_types: List[str] = Field(default_factory=list)
    affected_action_types: List[str] = Field(default_factory=list)
    affected_instances_count: int = 0
    breaking_changes: List[str] = Field(default_factory=list)
    estimated_migration_cost: str = "low"
    risk_level: str = "low"
    analysis_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ProposeChangeResponse(BaseModel):
    """propose-change 端点响应"""
    proposal: ProposalResponse
    impact: ImpactResponse


class ListProposalsResponse(BaseModel):
    """列出 ChangeProposal 响应"""
    proposals: List[ProposalResponse] = Field(default_factory=list)
    count: int = 0


class ReviewProposalRequest(BaseModel):
    """审批 Proposal 请求"""
    decision: str
    reviewer_notes: Optional[str] = None


class GoalLineageResponse(BaseModel):
    """Goal 血缘响应"""
    goal: Optional[GoalResponse] = None
    ancestors: List[GoalResponse] = Field(default_factory=list)
    children: List[GoalResponse] = Field(default_factory=list)
    proposals: List[ProposalResponse] = Field(default_factory=list)


__all__ = [
    "CreateGoalRequest",
    "UpdateGoalRequest",
    "GoalResponse",
    "ListGoalsResponse",
    "StatusTransitionRequest",
    "ProposeChangeRequest",
    "ProposalResponse",
    "ImpactResponse",
    "ProposeChangeResponse",
    "ListProposalsResponse",
    "ReviewProposalRequest",
    "GoalLineageResponse",
]
