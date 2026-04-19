"""本体构建模型"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from enum import Enum
from .audit import ProcessingStatus


class OntologyStatus(str, Enum):
    """本体状态"""
    DRAFT = "draft"
    VALIDATED = "validated"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class EntityExtractionResult(BaseModel):
    """实体提取结果"""
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    processing_time: float = 0.0


class OntologyBuildResult(BaseModel):
    """本体构建结果"""
    build_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_ingest_id: str
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


class OntologyDocument(BaseModel):
    """本体文档"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    status: OntologyStatus = OntologyStatus.DRAFT
    version: str = "1.0.0"
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    properties: List[Dict[str, Any]] = Field(default_factory=list)
    validation_rules: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    updated_by: str = "system"
