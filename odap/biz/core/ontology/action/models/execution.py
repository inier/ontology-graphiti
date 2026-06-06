"""ActionExecution 领域模型 (T377)

每次执行 ActionType 都会产生一条 ActionExecution 记录，包含：
- id: 执行 ID
- action_type_id: 关联的 ActionType
- parameters: 执行参数 (扁平 dict)
- result: 执行结果 (扁平 dict)
- status: PENDING / RUNNING / SUCCESS / FAILED / DENIED
- error_message: 错误描述
- audit_record_id: 关联的统一审计记录
- user_id / workspace_id: 调用上下文
- started_at / finished_at / duration_ms: 时延指标
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ActionExecutionStatus(str, Enum):
    """Action 执行状态枚举 (str, Enum) 双继承"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DENIED = "denied"  # OPA 拒绝


class ActionExecution(BaseModel):
    """Action Type 的一次执行实例

    与 unified_audit 通过 audit_record_id 关联，便于审计追溯。
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)
    status: ActionExecutionStatus = ActionExecutionStatus.PENDING
    error_message: str = ""
    audit_record_id: Optional[str] = None
    user_id: str = "system"
    workspace_id: str = "default"
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


__all__ = ["ActionExecution", "ActionExecutionStatus"]
