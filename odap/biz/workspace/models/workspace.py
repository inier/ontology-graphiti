"""工作空间模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum


class WorkspaceStatus(str, Enum):
    """工作空间状态"""
    CREATING = "creating"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETING = "deleting"
    ERROR = "error"


class WorkspaceType(str, Enum):
    """工作空间类型"""
    DEFAULT = "default"
    SHARED = "shared"
    PRIVATE = "private"
    TEMPORARY = "temporary"


class WorkspaceConfig(BaseModel):
    """工作空间配置"""
    isolation_level: str = "standard"
    resource_quota: Dict[str, Any] = Field(default_factory=dict)
    network_policy: Dict[str, Any] = Field(default_factory=dict)
    environment_vars: Dict[str, str] = Field(default_factory=dict)
    feature_flags: Dict[str, bool] = Field(default_factory=dict)


class Workspace(BaseModel):
    """工作空间"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    type: WorkspaceType = WorkspaceType.DEFAULT
    status: WorkspaceStatus = WorkspaceStatus.CREATING
    config: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    owner: str
    members: List[str] = Field(default_factory=list)
    resources: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_accessed_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
