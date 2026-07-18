from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class CreateSemanticMapRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    ontology_version_id: str = Field(..., min_length=1)
    ontology_id: str = Field(..., min_length=1)
    scenario_id: Optional[str] = None
    created_by: str = "system"
    generation_config: Optional[Dict[str, Any]] = None


class SemanticMapObjectResponse(BaseModel):
    object_id: str
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


class SemanticMapRelationResponse(BaseModel):
    relation_id: str
    source_object_id: str
    target_object_id: str
    relation_type: str
    display_name: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)
    is_bidirectional: bool = False


class SemanticMapClusterResponse(BaseModel):
    cluster_id: str
    cluster_name: str
    cluster_type: str
    object_ids: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)


class SemanticMapStatisticsResponse(BaseModel):
    total_objects: int = 0
    total_relations: int = 0
    total_clusters: int = 0
    objects_by_type: Dict[str, int] = Field(default_factory=dict)
    relations_by_type: Dict[str, int] = Field(default_factory=dict)
    avg_relations_per_object: float = 0.0
    coverage_score: float = 0.0


class SemanticMapResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    ontology_version_id: str
    ontology_id: str
    scenario_id: Optional[str] = None
    status: str
    objects: List[SemanticMapObjectResponse] = Field(default_factory=list)
    relations: List[SemanticMapRelationResponse] = Field(default_factory=list)
    clusters: List[SemanticMapClusterResponse] = Field(default_factory=list)
    statistics: SemanticMapStatisticsResponse = Field(default_factory=dict)
    generation_config: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: str = ""
    created_by: str = "system"
    updated_at: Optional[str] = None


class SemanticMapSummaryResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    ontology_version_id: str
    ontology_id: str
    scenario_id: Optional[str] = None
    status: str
    total_objects: int = 0
    total_relations: int = 0
    total_clusters: int = 0
    created_at: str = ""
    created_by: str = "system"


class SemanticMapListResponse(BaseModel):
    semantic_maps: List[SemanticMapSummaryResponse] = Field(default_factory=list)
    total: int = 0


class SemanticMapGraphResponse(BaseModel):
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    clusters: List[Dict[str, Any]] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
