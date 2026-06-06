"""Data Health - HealthReport 领域模型 (T333)

定义 3 种健康状态（pass/warn/fail）和扫描结果报告 Pydantic 模型。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field

from .rule import HealthSeverity


class HealthStatus(str, Enum):
    """健康检查结果状态"""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class HealthReport(BaseModel):
    """单次健康扫描结果"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    instance_id: str                                       # 被扫描的实例 ID
    target_type_id: str                                    # 实体类型 ID
    status: HealthStatus
    severity: HealthSeverity
    message: str = ""                                      # 描述
    details: Dict[str, Any] = Field(default_factory=dict)  # 详细数据
    scanned_at: datetime = Field(default_factory=datetime.now)


__all__ = ["HealthReport", "HealthStatus"]
