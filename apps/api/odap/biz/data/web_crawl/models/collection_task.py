"""CollectionTask 模型 - 数据采集任务追踪"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class CollectionTaskType(str, Enum):
    """采集任务类型"""
    SEARCH = "search"
    CRAWL = "crawl"
    BROWSER = "browser"


class CollectionTaskStatus(str, Enum):
    """采集任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DEGRADED = "degraded"


class CollectionTask(BaseModel):
    """采集任务"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: CollectionTaskType
    target: str
    status: CollectionTaskStatus = CollectionTaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    source: str = "external"
    confidence: str = "medium"
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
