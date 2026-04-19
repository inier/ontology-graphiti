"""数据摄入审计模型"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from enum import Enum


class DataSource(str, Enum):
    """数据来源"""
    API = "api"
    FILE = "file"
    DATABASE = "database"
    STREAM = "stream"
    MANUAL = "manual"


class ProcessingStatus(str, Enum):
    """处理状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DataIngestRecord(BaseModel):
    """数据摄入记录"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: DataSource
    source_details: Dict[str, Any] = Field(default_factory=dict)
    data_schema: Dict[str, Any] = Field(default_factory=dict)
    record_count: int = 0
    processed_count: int = 0
    failed_count: int = 0
    status: ProcessingStatus = ProcessingStatus.PENDING
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    quality_metrics: Dict[str, float] = Field(default_factory=dict)
    created_by: str = "system"


class AuditLog(BaseModel):
    """审计日志"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ingest_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    level: str = "info"
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    actor: str = "system"
