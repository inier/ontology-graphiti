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
    NEWS = "news"
    NATURAL_LANGUAGE = "natural_language"
    RANDOM = "random"
    QA_QUERY = "qa_query"


class ProcessingStatus(str, Enum):
    """处理状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(str, Enum):
    """处理管道阶段"""
    COLLECTION = "collection"       # 数据采集
    CLEANING = "cleaning"          # 数据清洗
    LLM_EXTRACTION = "llm"         # LLM归纳
    ONTOLOGY_BUILD = "ontology"    # 本体构建
    VERSION_MANAGE = "version"      # 版本管理
    GRAPH_BUILD = "graph"          # 图谱生成


class ProcessLog(BaseModel):
    """处理日志条目"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    stage: PipelineStage
    operation: str
    details: Dict[str, Any] = Field(default_factory=dict)
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None


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
    version_id: Optional[str] = None  # 关联的本体版本ID
    logs: List[ProcessLog] = Field(default_factory=list)  # 处理日志
    original_content: Optional[str] = None  # 原始内容


class AuditLog(BaseModel):
    """审计日志"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ingest_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    level: str = "info"
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    actor: str = "system"
