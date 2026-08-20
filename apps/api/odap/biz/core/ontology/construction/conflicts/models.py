"""冲突检测模型（ADR-078 §3.6）。

冲突标记而非覆盖：多源汇聚同一实体的属性/类型/关系/时态产生分歧时，
产出 Conflict 记录进入质量闸，而非静默覆盖。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConflictType(str, Enum):
    """冲突类型"""
    PROPERTY = "property"       # 属性值分歧
    TYPE = "type"               # 实体类型分歧
    RELATION = "relation"       # 关系分歧
    TEMPORAL = "temporal"       # 时态区间分歧


class ConflictSeverity(str, Enum):
    """冲突严重度"""
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class Conflict(BaseModel):
    """单条冲突记录"""
    conflict_id: str = Field(default_factory=lambda: f"conflict_{_gen_id()}")
    conflict_type: ConflictType
    entity_id: str                    # 冲突实体
    attribute: Optional[str] = None   # 冲突属性/关系名（property/relation 用）
    values: List[Any] = Field(default_factory=list)   # 冲突候选值（多源）
    sources: List[str] = Field(default_factory=list)  # 来源标识
    severity: ConflictSeverity = ConflictSeverity.WARN
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""
    resolved: bool = False            # 是否已消解
    resolution: Optional[Dict[str, Any]] = None  # 消解结果（胜出值/策略）


class ConflictReport(BaseModel):
    """冲突检测报告（进质量闸）"""
    workspace_id: str = "default"
    conflicts: List[Conflict] = Field(default_factory=list)
    total: int = 0
    resolved_count: int = 0
    unresolved_count: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def finalize(self) -> "ConflictReport":
        """统计并返回自身（链式）"""
        self.total = len(self.conflicts)
        self.resolved_count = sum(1 for c in self.conflicts if c.resolved)
        self.unresolved_count = self.total - self.resolved_count
        return self


def _gen_id() -> str:
    import uuid
    return uuid.uuid4().hex[:10]


__all__ = ["Conflict", "ConflictType", "ConflictSeverity", "ConflictReport"]
