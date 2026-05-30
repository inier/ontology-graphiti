from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum


class BlueprintNodeType(str, Enum):
    DATA_SOURCE = "data_source"
    TRANSFORM = "transform"
    ONTOLOGY = "ontology"
    ACTION = "action"
    VALIDATION = "validation"
    OUTPUT = "output"
    AGENT = "agent"
    DECISION = "decision"


class BlueprintEdgeType(str, Enum):
    DATA_FLOW = "data_flow"
    CONTROL_FLOW = "control_flow"
    DEPENDENCY = "dependency"


class CreateBlueprintRequest(BaseModel):
    name: str
    description: str = ""
    scenario_id: Optional[str] = None
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    layout: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateBlueprintRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    layout: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class AddNodeRequest(BaseModel):
    node_type: str
    name: str
    position: Optional[Dict[str, float]] = None
    config: Optional[Dict[str, Any]] = None


class UpdateNodeRequest(BaseModel):
    name: Optional[str] = None
    node_type: Optional[str] = None
    position: Optional[Dict[str, float]] = None
    config: Optional[Dict[str, Any]] = None


class AddEdgeRequest(BaseModel):
    source: str
    target: str
    edge_type: str = "data_flow"
    label: str = ""


class BatchAddNodesRequest(BaseModel):
    nodes: List[AddNodeRequest]


class BatchAddEdgesRequest(BaseModel):
    edges: List[AddEdgeRequest]


class BatchUpdatePositionsRequest(BaseModel):
    positions: Dict[str, Dict[str, float]]


class ImportBlueprintRequest(BaseModel):
    name: str
    data: Dict[str, Any]
    scenario_id: Optional[str] = None
