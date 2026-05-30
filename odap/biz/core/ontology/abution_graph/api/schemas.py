from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from ..models.types import TemporalDimension, PatternType, ForceType, ActionDimension

TemporalDimensionEnum = TemporalDimension
PatternTypeEnum = PatternType
ForceTypeEnum = ForceType
ActionDimensionEnum = ActionDimension


class TemporalNodeRequest(BaseModel):
    node_id: Optional[str] = None
    dimension: TemporalDimensionEnum
    timestamp: str
    description: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PatternNodeRequest(BaseModel):
    pattern_id: Optional[str] = None
    pattern_type: PatternTypeEnum
    name: str
    description: str
    evidence: List[str] = Field(default_factory=list)
    strength: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ForceNodeRequest(BaseModel):
    force_id: Optional[str] = None
    force_type: ForceTypeEnum
    name: str
    magnitude: float = 0.0
    direction: float = 0.0
    description: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionNodeRequest(BaseModel):
    action_id: Optional[str] = None
    dimension: ActionDimensionEnum
    name: str
    trigger_condition: str = ""
    effect: str = ""
    priority: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateSnapshotRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    temporal_nodes: List[TemporalNodeRequest] = Field(default_factory=list)
    pattern_nodes: List[PatternNodeRequest] = Field(default_factory=list)
    force_nodes: List[ForceNodeRequest] = Field(default_factory=list)
    action_nodes: List[ActionNodeRequest] = Field(default_factory=list)
    cross_dimension_links: List[Dict[str, str]] = Field(default_factory=list)


class AddDimensionNodeRequest(BaseModel):
    dimension: str = Field(..., pattern=r"^(temporal|pattern|force|action)$")
    node_data: Dict[str, Any]


class LinkDimensionsRequest(BaseModel):
    source_dim: str
    source_id: str
    target_dim: str
    target_id: str
    link_type: str = "correlation"
