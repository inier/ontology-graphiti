"""Hook模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum


class HookType(str, Enum):
    """Hook类型"""
    PRE_EXECUTE = "pre_execute"
    POST_EXECUTE = "post_execute"
    ON_ERROR = "on_error"
    ON_TIMEOUT = "on_timeout"
    PRE_commit = "pre_commit"
    POST_commit = "post_commit"


class HookStatus(str, Enum):
    """Hook状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class HookExecution(BaseModel):
    """Hook执行记录"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hook_id: str
    trigger_time: datetime = Field(default_factory=datetime.now)
    duration_ms: int = 0
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class Hook(BaseModel):
    """Hook"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    hook_type: HookType
    script: str
    language: str = "python"
    status: HookStatus = HookStatus.ACTIVE
    timeout_ms: int = 5000
    retry_count: int = 0
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
