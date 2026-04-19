"""API数据结构"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
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


class IsolationLevel(str, Enum):
    """隔离级别"""
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"
    STRICT = "strict"


class ImportExportStatus(str, Enum):
    """导入导出状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# 工作空间相关
class WorkspaceConfig(BaseModel):
    """工作空间配置"""
    isolation_level: str = "standard"
    resource_quota: Dict[str, Any] = Field(default_factory=dict)
    network_policy: Dict[str, Any] = Field(default_factory=dict)
    environment_vars: Dict[str, str] = Field(default_factory=dict)
    feature_flags: Dict[str, bool] = Field(default_factory=dict)


class CreateWorkspaceRequest(BaseModel):
    """创建工作空间请求"""
    name: str
    description: str = ""
    type: WorkspaceType = WorkspaceType.DEFAULT
    config: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    owner: str = "system"


class UpdateWorkspaceRequest(BaseModel):
    """更新工作空间请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[WorkspaceStatus] = None
    config: Optional[WorkspaceConfig] = None
    tags: Optional[List[str]] = None


class WorkspaceResponse(BaseModel):
    """工作空间响应"""
    workspace_id: str
    name: str
    description: str
    type: str
    status: str
    owner: str
    created_at: str
    updated_at: str


class WorkspaceDetailResponse(BaseModel):
    """工作空间详情响应"""
    workspace_id: str
    name: str
    description: str
    type: str
    status: str
    config: Dict[str, Any]
    owner: str
    members: List[str]
    resources: Dict[str, Any]
    created_at: str
    updated_at: str
    last_accessed_at: Optional[str] = None
    tags: List[str]


class WorkspaceListResponse(BaseModel):
    """工作空间列表响应"""
    workspaces: List[Dict[str, Any]]
    page: int
    page_size: int
    total: int


# 隔离相关
class ResourceQuota(BaseModel):
    """资源配额"""
    cpu: Optional[str] = None
    memory: Optional[str] = None
    storage: Optional[str] = None
    max_connections: Optional[int] = None
    max_processes: Optional[int] = None


class NetworkPolicy(BaseModel):
    """网络策略"""
    allowed_ips: List[str] = Field(default_factory=list)
    blocked_ips: List[str] = Field(default_factory=list)
    allowed_ports: List[int] = Field(default_factory=list)
    blocked_ports: List[int] = Field(default_factory=list)
    enable_firewall: bool = True


class CreateIsolationPolicyRequest(BaseModel):
    """创建隔离策略请求"""
    workspace_id: str
    isolation_level: IsolationLevel = IsolationLevel.STANDARD
    resource_quota: Optional[ResourceQuota] = None
    network_policy: Optional[NetworkPolicy] = None


class IsolationPolicyResponse(BaseModel):
    """隔离策略响应"""
    workspace_id: str
    isolation_level: str
    resource_quota: Dict[str, Any]
    network_policy: Dict[str, Any]
    created_at: str


class ResourceUsageResponse(BaseModel):
    """资源使用情况响应"""
    workspace_id: str
    cpu_usage: float
    memory_usage: float
    storage_usage: float
    connections: int
    processes: int
    timestamp: str


# 导入导出相关
class ExportWorkspaceRequest(BaseModel):
    """导出工作空间请求"""
    workspace_id: str
    export_path: Optional[str] = None
    include_resources: bool = True
    include_data: bool = False
    created_by: str = "system"


class ImportWorkspaceRequest(BaseModel):
    """导入工作空间请求"""
    import_path: str
    workspace_name: Optional[str] = None
    overwrite: bool = False
    created_by: str = "system"


class ImportExportResponse(BaseModel):
    """导入导出响应"""
    record_id: str
    workspace_id: str
    operation: str
    status: str
    progress: float
    start_time: str


class ImportExportStatusResponse(BaseModel):
    """导入导出状态响应"""
    record_id: str
    operation: str
    status: str
    progress: float
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None


class ImportExportListResponse(BaseModel):
    """导入导出列表响应"""
    records: List[Dict[str, Any]]
    page: int
    page_size: int
    total: int


# 通用响应
class SuccessResponse(BaseModel):
    """成功响应"""
    status: str = "success"
    message: str


class ErrorResponse(BaseModel):
    """错误响应"""
    status: str = "error"
    message: str
