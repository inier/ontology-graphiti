from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class SemanticMapStatus(str, Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class SemanticMapObject(BaseModel):
    object_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str
    object_type: str
    name: str
    name_en: str = ""
    aliases: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)
    type_definition_id: Optional[str] = None
    type_definition_name: Optional[str] = None
    relation_ids: List[str] = Field(default_factory=list)
    cluster: Optional[str] = None
    confidence: float = 1.0


class SemanticMapRelation(BaseModel):
    relation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_object_id: str
    target_object_id: str
    relation_type: str
    display_name: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)
    is_bidirectional: bool = False
    temporal_start: Optional[str] = None
    temporal_end: Optional[str] = None
    is_current: bool = True


class SemanticMapCluster(BaseModel):
    cluster_id: str
    cluster_name: str
    cluster_type: str
    object_ids: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)


class SemanticMapStatistics(BaseModel):
    total_objects: int = 0
    total_relations: int = 0
    total_clusters: int = 0
    objects_by_type: Dict[str, int] = Field(default_factory=dict)
    relations_by_type: Dict[str, int] = Field(default_factory=dict)
    avg_relations_per_object: float = 0.0
    coverage_score: float = 0.0


class SemanticMap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    ontology_version_id: str
    ontology_id: str
    scenario_id: Optional[str] = None
    status: SemanticMapStatus = SemanticMapStatus.DRAFT
    objects: List[SemanticMapObject] = Field(default_factory=list)
    relations: List[SemanticMapRelation] = Field(default_factory=list)
    clusters: List[SemanticMapCluster] = Field(default_factory=list)
    statistics: SemanticMapStatistics = Field(default_factory=SemanticMapStatistics)
    generation_config: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    updated_at: Optional[datetime] = None


class SemanticMapSummary(BaseModel):
    id: str
    name: str
    description: str
    ontology_version_id: str
    ontology_id: str
    scenario_id: Optional[str] = None
    status: SemanticMapStatus
    total_objects: int = 0
    total_relations: int = 0
    total_clusters: int = 0
    created_at: datetime
    created_by: str
