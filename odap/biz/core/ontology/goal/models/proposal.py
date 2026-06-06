"""ChangeProposal 领域模型 (T417)

针对 Goal 的结构化变更提案，使用 JSON Patch 格式描述要修改的内容。
JSON Patch (RFC 6902) 提供了 op/path/value 三元组的最小变更描述。

示例:
    [
      {"op": "add", "path": "/object_types/Person/properties/age", "value": {...}},
      {"op": "replace", "path": "/object_types/Person/required/0", "value": "name"},
      {"op": "remove", "path": "/action_types/SendEmail"}
    ]
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ProposalStatus(str, Enum):
    """提案状态枚举 (str, Enum) 双继承"""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under-review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


# 合法状态机转换
PROPOSAL_STATE_TRANSITIONS: Dict[ProposalStatus, List[ProposalStatus]] = {
    ProposalStatus.DRAFT: [ProposalStatus.SUBMITTED],
    ProposalStatus.SUBMITTED: [ProposalStatus.UNDER_REVIEW,
                               ProposalStatus.REJECTED],
    ProposalStatus.UNDER_REVIEW: [ProposalStatus.APPROVED,
                                  ProposalStatus.REJECTED],
    ProposalStatus.APPROVED: [ProposalStatus.IMPLEMENTED],
    ProposalStatus.REJECTED: [],
    ProposalStatus.IMPLEMENTED: [],
}


class ChangeProposal(BaseModel):
    """针对 Goal 的结构化变更提案

    Attributes:
        id: UUID4 (auto)
        goal_id: 关联的 Goal ID
        title: 提案标题
        description: 变更详细说明
        changes: JSON Patch 列表 (RFC 6902)
        impact_analysis_id: 关联的 ImpactAnalysis ID (创建后回填)
        estimated_benefit: 预期收益描述
        estimated_cost: 预期成本描述
        status: 当前状态 (默认 draft)
        proposed_by: 提案人
        created_at: 提案时间
        reviewed_at: 审批时间
        reviewer_notes: 审批人备注
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str
    title: str
    description: str = ""
    changes: List[Dict[str, Any]] = Field(default_factory=list)
    impact_analysis_id: Optional[str] = None
    estimated_benefit: str = ""
    estimated_cost: Optional[str] = None
    status: ProposalStatus = ProposalStatus.DRAFT
    proposed_by: str
    created_at: datetime = Field(default_factory=datetime.now)
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None

    @model_validator(mode="after")
    def _validate_goal_id(self) -> "ChangeProposal":
        """goal_id 非空校验"""
        if not self.goal_id or not self.goal_id.strip():
            raise ValueError("goal_id is required and must be non-empty")
        return self

    @model_validator(mode="after")
    def _validate_title(self) -> "ChangeProposal":
        """title 非空校验"""
        if not self.title or not self.title.strip():
            raise ValueError("title is required and must be non-empty")
        return self

    @model_validator(mode="after")
    def _validate_changes_format(self) -> "ChangeProposal":
        """验证 changes 中每个元素都包含 op/path 字段"""
        allowed_ops = {"add", "remove", "replace", "move", "copy", "test"}
        for i, change in enumerate(self.changes or []):
            if not isinstance(change, dict):
                raise ValueError(
                    f"changes[{i}] must be a dict, got {type(change).__name__}"
                )
            if "op" not in change:
                raise ValueError(f"changes[{i}] missing required field 'op'")
            if "path" not in change:
                raise ValueError(
                    f"changes[{i}] missing required field 'path'"
                )
            if change["op"] not in allowed_ops:
                raise ValueError(
                    f"changes[{i}].op '{change['op']}' not in {allowed_ops}"
                )
        return self


__all__ = ["ChangeProposal", "ProposalStatus", "PROPOSAL_STATE_TRANSITIONS"]
