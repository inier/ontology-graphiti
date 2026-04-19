"""审计日志模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogType(str, Enum):
    """日志类型"""
    ACCESS = "access"
    OPERATION = "operation"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ERROR = "error"
    AUDIT = "audit"


class LogStatus(str, Enum):
    """日志状态"""
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"


class AuditLog(BaseModel):
    """审计日志"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    level: LogLevel = LogLevel.INFO
    type: LogType = LogType.AUDIT
    service: str
    action: str
    resource: Optional[str] = None
    user: Optional[str] = None
    ip_address: Optional[str] = None
    status: LogStatus = LogStatus.PENDING
    duration_ms: Optional[int] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tags: List[str] = Field(default_factory=list)
    processed_at: Optional[datetime] = None
    block_id: Optional[str] = None
