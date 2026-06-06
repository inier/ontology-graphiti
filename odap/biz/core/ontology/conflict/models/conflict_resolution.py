"""
冲突解决 - 领域模型 (T313)

定义 4 种冲突解决策略 + 冲突记录 / 解决结果 Pydantic 模型。
对齐 AGENTS.md 规则 4 (Enum 必须 (str, Enum) 双继承) 与规则 5
(容器字段必须 Field(default_factory=...))。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ConflictResolution(str, Enum):
    """冲突解决策略（必须 (str, Enum) 双继承，便于 JSON 序列化）"""
    FIRST_WINS = "first_wins"     # 取最早源
    LAST_WINS = "last_wins"       # 取最新源
    LLM_JUDGE = "llm_judge"       # 调用 LLM 判断
    MANUAL = "manual"             # 标记待人工处理


class ConflictStatus(str, Enum):
    """冲突处理状态"""
    PENDING = "pending"           # 待处理
    RESOLVED = "resolved"         # 已解决
    ABANDONED = "abandoned"       # 已放弃
    AWAITING_HUMAN = "awaiting_human"  # 等待人工


class ConflictType(str, Enum):
    """冲突类型"""
    VALUE_MISMATCH = "value_mismatch"     # 字段值不同
    SCHEMA_DRIFT = "schema_drift"         # schema 不一致
    MISSING_FIELD = "missing_field"       # 字段缺失
    TYPE_INCOMPATIBLE = "type_incompatible"  # 类型不兼容


class ConflictCandidate(BaseModel):
    """冲突候选值（来自不同数据源）"""
    source_id: str                                  # 数据源 ID
    value: Any                                      # 候选值
    confidence: float = 1.0                         # 置信度 0-1
    observed_at: datetime = Field(default_factory=datetime.now)  # 观察到的时间
    metadata: Dict[str, Any] = Field(default_factory=dict)       # 附加元数据


class ConflictRecord(BaseModel):
    """冲突记录"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    entity_id: str                                 # 冲突的实体/对象 ID
    entity_type: str                               # 实体类型
    field_name: str                                # 冲突字段
    conflict_type: ConflictType = ConflictType.VALUE_MISMATCH
    candidates: List[ConflictCandidate] = Field(default_factory=list)  # 容器字段
    status: ConflictStatus = ConflictStatus.PENDING
    strategy: Optional[ConflictResolution] = None   # 已选策略
    chosen: Optional[ConflictCandidate] = None      # 选定的候选
    detected_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolver_id: Optional[str] = None               # 解决者（用户 ID / "llm" / "auto"）
    notes: str = ""                                # 解决备注


class ResolutionResult(BaseModel):
    """冲突解决结果"""
    conflict_id: str
    status: ConflictStatus
    chosen: Optional[ConflictCandidate] = None
    rationale: str = ""                            # 解决理由（LLM_JUDGE 时为 LLM 输出）
    strategy_used: ConflictResolution
    duration_ms: float = 0.0                       # 解决耗时
