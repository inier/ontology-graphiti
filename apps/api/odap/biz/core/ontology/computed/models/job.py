"""MaterializationJob 领域模型 (T392)

物化任务：每次触发重算（手动 / 增量 / 定时）都会创建一条 MaterializationJob，
记录执行状态、处理的实例数、错误信息和触发来源。

对齐 AGENTS.md 规则 4 (Enum 必须 (str, Enum) 双继承)。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MaterializationStatus(str, Enum):
    """物化任务状态枚举 (str, Enum) 双继承"""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class JobTrigger(str, Enum):
    """物化任务触发来源 (str, Enum) 双继承"""
    MANUAL = "manual"
    INCREMENTAL = "incremental"
    SCHEDULED = "scheduled"


class MaterializationJob(BaseModel):
    """物化任务实例

    与 ComputedProperty 通过 property_id 关联，便于追溯
    "哪个属性的哪次重算影响了哪些实例"。
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    property_id: str
    status: MaterializationStatus = MaterializationStatus.PENDING
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    processed_count: int = 0
    error_message: str = ""
    triggered_by: JobTrigger = JobTrigger.MANUAL
    mode: str = "incremental"  # "full" | "incremental"


__all__ = ["MaterializationJob", "MaterializationStatus", "JobTrigger"]
