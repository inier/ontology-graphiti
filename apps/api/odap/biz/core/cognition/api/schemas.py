from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RecognizeIntentRequest(BaseModel):
    input_text: str
    role: str = "guest"
    ontology_facts: List[str] = Field(default_factory=list)


class RecognizeIntentResponse(BaseModel):
    intent_id: Optional[str] = None
    primary_intent: Optional[str] = None
    confidence: float = 0.0
    entities: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    alternative_intents: List[str] = Field(default_factory=list)


class NavigateRequest(BaseModel):
    entity_id: str
    direction: str = "outbound"
    depth: int = 1


class NavigateResponse(BaseModel):
    navigation_id: Optional[str] = None
    entity_id: str = ""
    navigation_path: List[str] = Field(default_factory=list)
    related_entities: List[Dict[str, Any]] = Field(default_factory=list)
    entity_context: Dict[str, Any] = Field(default_factory=dict)


class ExplainRequest(BaseModel):
    decision_id: str
    context: Dict[str, Any] = Field(default_factory=dict)


class ExplainResponse(BaseModel):
    explanation_id: Optional[str] = None
    decision_id: str = ""
    query: str = ""
    answer: str = ""
    confidence: float = 0.0
    reasoning_chain: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)


class RoleViewResponse(BaseModel):
    view_id: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    layout_config: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)


class UpdateRoleViewRequest(BaseModel):
    role: str
    capabilities: List[str] = Field(default_factory=list)
    layout_config: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)
    name: Optional[str] = None
    description: Optional[str] = None
