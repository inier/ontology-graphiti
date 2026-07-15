"""ImpactAnalysis 领域模型 (T418)

变更影响分析：静态分析 JSON Patch 的 path 字段，识别受影响的 ObjectType /
ActionType、估算迁移成本与风险等级。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ImpactCost(str, Enum):
    """迁移成本枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(str, Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactAnalysis(BaseModel):
    """变更影响分析结果

    Attributes:
        id: UUID4 (auto)
        proposal_id: 关联的 ChangeProposal ID
        affected_object_types: 受影响的 ObjectType ID 列表
        affected_action_types: 受影响的 ActionType ID 列表
        affected_instances_count: 估算受影响的实例数
        breaking_changes: 破坏性变更描述列表
        estimated_migration_cost: 估算迁移成本 (low/medium/high)
        risk_level: 风险等级 (low/medium/high/critical)
        analysis_metadata: 附加分析元数据
        created_at: 创建时间
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id: str = ""  # 可选：静态分析时可能尚未关联 proposal
    affected_object_types: List[str] = Field(default_factory=list)
    affected_action_types: List[str] = Field(default_factory=list)
    affected_instances_count: int = 0
    breaking_changes: List[str] = Field(default_factory=list)
    estimated_migration_cost: ImpactCost = ImpactCost.LOW
    risk_level: RiskLevel = RiskLevel.LOW
    analysis_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


__all__ = ["ImpactAnalysis", "ImpactCost", "RiskLevel"]
