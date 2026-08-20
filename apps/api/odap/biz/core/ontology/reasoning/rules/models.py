"""BusinessRule — 确定性推理规则领域模型 (ADR-075 §3)。

规则载体（TBox）：
- 使用 Datalog 子句语法（head <= body），body 为合取式。
- 随本体版本管理：valid_from 记录生效时刻，version_id 关联本体版本。
- 规则安全由 rule_loader 白名单校验（本文件不校验，仅建模）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class RulePriority(str, Enum):
    """规则优先级（冲突消解顺序）"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class BusinessRule(BaseModel):
    """确定性推理规则（Datalog 子句）"""

    rule_id: str = Field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:12]}")
    ontology_id: str                                  # 所属本体
    workspace_id: str = "default"                     # 隔离边界（必填，非空校验）
    name: str                                         # 规则名称
    description: str = ""                             # 规则描述
    rule_text: str                                    # Datalog 子句文本（head <= body）
    enabled: bool = True                              # 是否启用
    priority: RulePriority = RulePriority.NORMAL      # 优先级
    valid_from: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"                        # 创建者
    version_id: Optional[str] = None                  # 关联本体版本（§3.2 回滚联动）
    metadata: Dict[str, Any] = Field(default_factory=dict)  # 扩展元数据

    @field_validator("workspace_id")
    @classmethod
    def _workspace_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("workspace_id 不能为空")
        return v.strip()

    @field_validator("rule_text")
    @classmethod
    def _rule_text_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("rule_text 不能为空")
        return v.strip()

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name 不能为空")
        return v.strip()


def to_storage_dict(rule: BusinessRule) -> Dict[str, Any]:
    """序列化为 storage 行字典"""
    return {
        "rule_id": rule.rule_id,
        "ontology_id": rule.ontology_id,
        "workspace_id": rule.workspace_id,
        "name": rule.name,
        "description": rule.description,
        "rule_text": rule.rule_text,
        "enabled": 1 if rule.enabled else 0,
        "priority": rule.priority.value,
        "valid_from": rule.valid_from.isoformat(),
        "created_by": rule.created_by,
        "version_id": rule.version_id,
        "metadata": rule.metadata,
    }


def from_storage_dict(row: Dict[str, Any]) -> BusinessRule:
    """从 storage 行字典反序列化"""
    return BusinessRule(
        rule_id=row["rule_id"],
        ontology_id=row["ontology_id"],
        workspace_id=row["workspace_id"],
        name=row["name"],
        description=row.get("description", ""),
        rule_text=row["rule_text"],
        enabled=bool(row.get("enabled", 1)),
        priority=RulePriority(row.get("priority", "normal")),
        valid_from=datetime.fromisoformat(row["valid_from"]),
        created_by=row.get("created_by", "system"),
        version_id=row.get("version_id"),
        metadata=row.get("metadata") or {},
    )


__all__ = ["BusinessRule", "RulePriority", "to_storage_dict", "from_storage_dict"]
