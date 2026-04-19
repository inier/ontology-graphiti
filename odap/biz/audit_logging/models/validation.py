"""验证模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum


class ValidationStatus(str, Enum):
    """验证状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class ValidationResult(BaseModel):
    """验证结果"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    block_id: str
    chain_id: str
    status: ValidationStatus = ValidationStatus.PENDING
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    issue_count: int = 0
    is_valid: bool = False
    created_at: datetime = Field(default_factory=datetime.now)


class ValidationIssue(BaseModel):
    """验证问题"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    validation_id: str
    block_id: str
    issue_type: str
    severity: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
