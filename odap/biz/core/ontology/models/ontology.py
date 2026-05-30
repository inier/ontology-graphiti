import warnings
warnings.warn(
    "odap.biz.core.ontology.models.ontology.OntologyDocument is deprecated. "
    "Use odap.biz.core.ontology.schema.document.OntologyDocument instead.",
    DeprecationWarning,
    stacklevel=2,
)
from odap.biz.core.ontology.schema.document import OntologyDocument
from odap.biz.core.ontology.models.audit import ProcessingStatus
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from enum import Enum


class OntologyStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class EntityExtractionResult(BaseModel):
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    processing_time: float = 0.0


class OntologyBuildResult(BaseModel):
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
