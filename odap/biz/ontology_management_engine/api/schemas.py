"""API数据结构"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
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


class OntologyStatus(str, Enum):
    """本体状态"""
    DRAFT = "draft"
    VALIDATED = "validated"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class ValidationSeverity(str, Enum):
    """验证严重程度"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# 数据摄入相关
class IngestRequest(BaseModel):
    """摄入请求"""
    source: DataSource
    source_details: Dict[str, Any] = Field(default_factory=dict)
    data: Dict[str, Any]


class IngestResponse(BaseModel):
    """摄入响应"""
    ingest_id: str
    status: str


class IngestStatusResponse(BaseModel):
    """摄入状态响应"""
    ingest_id: str
    source: str
    status: str
    processed_count: int
    failed_count: int
    total_count: int
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    quality_metrics: Dict[str, float]


class IngestListResponse(BaseModel):
    """摄入列表响应"""
    jobs: List[Dict[str, Any]]
    page: int
    page_size: int
    total: int


# 本体构建相关
class CreateOntologyRequest(BaseModel):
    """创建本体请求"""
    name: str
    description: str = ""


class UpdateOntologyRequest(BaseModel):
    """更新本体请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    entities: Optional[List[Dict[str, Any]]] = None
    relations: Optional[List[Dict[str, Any]]] = None
    properties: Optional[List[Dict[str, Any]]] = None
    status: Optional[OntologyStatus] = None


class OntologyResponse(BaseModel):
    """本体响应"""
    ontology_id: str
    name: str
    description: str
    status: str
    version: str
    entity_count: int
    relation_count: int
    created_at: str
    updated_at: str


class OntologyListResponse(BaseModel):
    """本体列表响应"""
    ontologies: List[Dict[str, Any]]
    page: int
    page_size: int
    total: int


class BuildFromIngestResponse(BaseModel):
    """从摄入构建响应"""
    status: str
    build_id: str
    ontology_id: str
    entity_count: int
    relation_count: int
    build_time: float


# 版本管理相关
class CreateVersionRequest(BaseModel):
    """创建版本请求"""
    ontology_id: str
    version_number: str
    parent_version_id: Optional[str] = None
    change_summary: str = ""


class VersionResponse(BaseModel):
    """版本响应"""
    version_id: str
    ontology_id: str
    version_number: str
    parent_version_id: Optional[str] = None
    status: str
    change_summary: str
    created_at: str
    is_current: bool


class VersionListResponse(BaseModel):
    """版本列表响应"""
    versions: List[Dict[str, Any]]
    page: int
    page_size: int
    total: int


class RollbackVersionRequest(BaseModel):
    """回滚版本请求"""
    ontology_id: str
    target_version_id: str


class CompareVersionsRequest(BaseModel):
    """对比版本请求"""
    source_version_id: str
    target_version_id: str


class MergeVersionsRequest(BaseModel):
    """合并版本请求"""
    ontology_id: str
    source_version_id: str
    target_version_id: str
    conflict_resolution: Optional[Dict[str, Any]] = None


# 验证相关
class CreateValidationRuleRequest(BaseModel):
    """创建验证规则请求"""
    name: str
    description: str = ""
    rule_type: str
    severity: ValidationSeverity = ValidationSeverity.WARNING
    expression: str
    params: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ValidationRuleResponse(BaseModel):
    """验证规则响应"""
    rule_id: str
    name: str
    description: str
    rule_type: str
    severity: str
    expression: str
    enabled: bool


class ValidationRuleListResponse(BaseModel):
    """验证规则列表响应"""
    rules: List[Dict[str, Any]]
    page: int
    page_size: int
    total: int


class ValidateOntologyRequest(BaseModel):
    """验证本体请求"""
    ontology_id: str
    rules: Optional[List[str]] = None


class ValidationResultResponse(BaseModel):
    """验证结果响应"""
    result_id: str
    ontology_id: str
    ontology_version: str
    status: str
    error_count: int
    warning_count: int
    info_count: int
    overall_score: float
    duration_seconds: float
    validation_time: str


class FixValidationIssueRequest(BaseModel):
    """修复验证问题请求"""
    issue_id: str
    fix_action: Dict[str, Any]


# 审计仪表盘相关
class DashboardSummaryResponse(BaseModel):
    """仪表盘摘要响应"""
    ingest_summary: Dict[str, Any]
    ontology_summary: Dict[str, Any]
    validation_summary: Dict[str, Any]
    version_summary: Dict[str, Any]


class PerformanceMetricsResponse(BaseModel):
    """性能指标响应"""
    average_ingest_time: float
    average_build_time: float
    average_validation_time: float
    system_load: float


class ErrorTrendsResponse(BaseModel):
    """错误趋势响应"""
    trends: List[Dict[str, Any]]


class TopIssuesResponse(BaseModel):
    """Top问题响应"""
    issues: List[Dict[str, Any]]
