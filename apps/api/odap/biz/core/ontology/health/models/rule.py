"""Data Health - HealthRule 领域模型 (T332)

定义 5 种规则类型（not_null/unique/regex/range/referential_integrity）
和 4 级严重度（info/warning/error/critical）。

对齐 AGENTS.md 规则 4 (Enum 必须 (str, Enum) 双继承) 与规则 5
(容器字段必须 Field(default_factory=...))。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


class HealthSeverity(str, Enum):
    """健康严重度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthRuleType(str, Enum):
    """健康规则类型"""
    NOT_NULL = "not_null"
    UNIQUE = "unique"
    REGEX = "regex"
    RANGE = "range"
    REFERENTIAL_INTEGRITY = "referential_integrity"


class HealthRule(BaseModel):
    """数据健康检查规则"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_type_id: str                                    # 目标实体类型 ID
    name: str                                              # 规则名称
    description: str = ""                                  # 规则描述
    rule_type: str = HealthRuleType.NOT_NULL.value         # 规则类型
    check_expression: Dict[str, Any] = Field(default_factory=dict)  # 规则表达式 (JSON/YAML)
    severity: HealthSeverity = HealthSeverity.WARNING      # 严重度
    schedule: str = ""                                     # cron 表达式（可选）
    notification_channel: Dict[str, Any] = Field(default_factory=dict)  # 通知通道配置
    enabled: bool = True                                   # 是否启用
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


__all__ = ["HealthRule", "HealthSeverity", "HealthRuleType"]
