import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# IntentType 统一从 ontology/common/ 导入（源定义，消除重复）
from odap.biz.core.ontology.common.types import IntentType  # noqa: E402


class IntentResult(BaseModel):
    intent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    primary_intent: IntentType = IntentType.QUERY
    confidence: float = 0.0
    entities: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    alternative_intents: List[str] = Field(default_factory=list)
    role: str = "guest"


class NavigationPathNode(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    label: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)


class NavigationPathEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    relation_type: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)


class NavigationPath(BaseModel):
    navigation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    direction: str = "outbound"
    depth: int = 1
    path_nodes: List[str] = Field(default_factory=list)
    related_entities: List[Dict[str, Any]] = Field(default_factory=list)
    entity_context: Dict[str, Any] = Field(default_factory=dict)


class ReasoningStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_type: str = "premise"
    description: str = ""
    confidence: float = 0.0


class Explanation(BaseModel):
    explanation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    query: str = ""
    answer: str = ""
    confidence: float = 0.0
    reasoning_chain: List[ReasoningStep] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    alternative_explanations: List[str] = Field(default_factory=list)


class RoleViewConfig(BaseModel):
    view_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str = "guest"
    name: str = ""
    description: str = ""
    capabilities: List[str] = Field(default_factory=list)
    layout_config: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)
