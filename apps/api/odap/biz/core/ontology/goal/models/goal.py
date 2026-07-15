"""Goal 领域模型 (T416)

OntoFlow Goal 驱动的核心实体：业务目标是本体演化的"第一类公民"。

状态机:
    proposed -> approved | rejected
    approved -> in-progress
    in-progress -> achieved | abandoned

parent_goal_id 允许父子 Goal 嵌套，构成 Goal Lineage 树。
rationale 由 LLM Rationale Generator 多轮追问生成 (可空)。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class GoalStatus(str, Enum):
    """Goal 状态枚举 (str, Enum) 双继承 — 满足 AGENTS.md 规则 4"""
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in-progress"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"


# 合法状态机转换: from -> set(to)
GOAL_STATE_TRANSITIONS: Dict[GoalStatus, List[GoalStatus]] = {
    GoalStatus.PROPOSED: [GoalStatus.APPROVED, GoalStatus.REJECTED],
    GoalStatus.APPROVED: [GoalStatus.IN_PROGRESS],
    GoalStatus.IN_PROGRESS: [GoalStatus.ACHIEVED, GoalStatus.ABANDONED],
    GoalStatus.REJECTED: [],
    GoalStatus.ACHIEVED: [],
    GoalStatus.ABANDONED: [],
}


def is_valid_goal_transition(src: GoalStatus, dst: GoalStatus) -> bool:
    """判断状态机转换是否合法"""
    if src == dst:
        return True
    return dst in GOAL_STATE_TRANSITIONS.get(src, [])


class Goal(BaseModel):
    """业务目标 / 本体演化目标

    Attributes:
        id: UUID4 (auto)
        title: 目标标题 (必填)
        description: 详细描述
        business_objective: 业务层面要达成的结果 (必填)
        rationale: LLM 生成的多轮追问后的业务合理性说明
        status: 当前状态 (默认 proposed)
        parent_goal_id: 父 Goal ID，支持父子嵌套
        workspace_id: 所属工作空间
        created_by: 创建者
        created_at / updated_at: 时间戳
        tags: 标签
        metadata: 任意元数据
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str = ""
    business_objective: str
    rationale: Optional[str] = None
    status: GoalStatus = GoalStatus.PROPOSED
    parent_goal_id: Optional[str] = None
    workspace_id: str
    created_by: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_title(self) -> "Goal":
        """title 非空校验"""
        if not self.title or not self.title.strip():
            raise ValueError("title is required and must be non-empty")
        return self

    @model_validator(mode="after")
    def _validate_business_objective(self) -> "Goal":
        """business_objective 非空校验"""
        if not self.business_objective or not self.business_objective.strip():
            raise ValueError(
                "business_objective is required and must be non-empty"
            )
        return self

    @model_validator(mode="after")
    def _validate_workspace(self) -> "Goal":
        """workspace_id 非空校验"""
        if not self.workspace_id or not self.workspace_id.strip():
            raise ValueError("workspace_id is required and must be non-empty")
        return self

    @model_validator(mode="after")
    def _validate_no_self_parent(self) -> "Goal":
        """不能将自己设为父 Goal"""
        if self.parent_goal_id and self.parent_goal_id == self.id:
            raise ValueError("parent_goal_id cannot equal self.id")
        return self


__all__ = ["Goal", "GoalStatus", "GOAL_STATE_TRANSITIONS",
           "is_valid_goal_transition"]
