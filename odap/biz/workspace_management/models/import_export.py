"""导入导出模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum


class ImportExportStatus(str, Enum):
    """导入导出状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportExportRecord(BaseModel):
    """导入导出记录"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str
    operation: str  # import/export
    status: ImportExportStatus = ImportExportStatus.PENDING
    source: Optional[str] = None
    destination: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    progress: float = 0.0
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    created_by: str
