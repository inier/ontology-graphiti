"""
本体管理引擎数据模型 - 对齐 docs/03-modules/ontology_management_engine/DESIGN.md

包含:
- 数据摄入审计模型
- 本体构建模型
- 版本管理模型
- 验证引擎模型
- 审计仪表盘模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

from odap.biz.core.ontology.schema.document import OntologyDocument as FullOntologyDocument


class DataSource(str, Enum):
    API = "api"
    FILE = "file"
    DATABASE = "database"
    STREAM = "stream"
    MANUAL = "manual"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OntologyStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class VersionOperation(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    ROLLBACK = "rollback"
    MERGE = "merge"
    DELETE = "delete"


class VersionStatus(str, Enum):
    DRAFT = "draft"
    RELEASED = "released"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class QualityMetricType(str, Enum):
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    ACCURACY = "accuracy"
    TIMELINESS = "timeliness"
    UNIQUENESS = "uniqueness"


class AnomalyType(str, Enum):
    MISSING_REQUIRED = "missing_required"
    DUPLICATE_ENTITY = "duplicate_entity"
    INVALID_RELATION = "invalid_relation"
    BROKEN_REFERENCE = "broken_reference"
    TYPE_MISMATCH = "type_mismatch"


class DataIngestRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: DataSource = DataSource.API
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
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ingest_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    level: str = "info"
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    actor: str = "system"


class EntityExtractionResult(BaseModel):
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    processing_time: float = 0.0


class OntologyBuildResult(BaseModel):
    build_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_ingest_id: str = ""
    entity_count: int = 0
    relation_count: int = 0
    property_count: int = 0
    status: ProcessingStatus = ProcessingStatus.PENDING
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    ontology_version: str = "1.0.0"


# 向后兼容别名: 统一使用 schema.document.OntologyDocument (dataclass)
# 注意: 完整版字段结构与简化版不同，消费方需适配
#   简化版 id/name/description/created_by/updated_by 等字段在完整版中
#   对应 doc_id/meta.title/meta.description 等
OntologyDocument = FullOntologyDocument


class VersionChange(BaseModel):
    change_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    field: str = ""
    old_value: Any = None
    new_value: Any = None
    change_type: str = "update"
    timestamp: datetime = Field(default_factory=datetime.now)
    changed_by: str = "system"


class VersionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version_number: str = "1.0.0"
    status: VersionStatus = VersionStatus.DRAFT
    changes: List[VersionChange] = Field(default_factory=list)
    snapshot: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    parent_version: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    tags: List[str] = Field(default_factory=list)


class ValidationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    rule_type: str = ""
    severity: str = "warning"
    condition: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ValidationError(BaseModel):
    rule_id: str = ""
    entity_id: Optional[str] = None
    field: str = ""
    message: str = ""
    severity: str = "warning"


class ValidationResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ontology_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    passed: bool = True
    total_rules: int = 0
    passed_rules: int = 0
    failed_rules: int = 0
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list)
    quality_scores: Dict[str, float] = Field(default_factory=dict)
    duration_seconds: float = 0.0


class AnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_type: AnomalyType = AnomalyType.MISSING_REQUIRED
    entity_id: Optional[str] = None
    field: str = ""
    description: str = ""
    severity: str = "warning"
    detected_at: datetime = Field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class AuditDashboardData(BaseModel):
    total_ingests: int = 0
    total_entities: int = 0
    total_relations: int = 0
    build_success_rate: float = 0.0
    validation_pass_rate: float = 0.0
    recent_anomalies: List[AnomalyRecord] = Field(default_factory=list)
    quality_trends: Dict[str, List[float]] = Field(default_factory=dict)
    version_history: List[Dict[str, Any]] = Field(default_factory=list)


class OntologyHealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"
