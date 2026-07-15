"""T065 Pydantic models for AI assistant.

Request/response schemas for AG-UI protocol, suggestions, and rule engine.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    session_id: Optional[str] = None
    ontology_id: str
    context_type: str = "object_type_editor"
    context_id: Optional[str] = None
    message: str


class ResumeRequest(BaseModel):
    run_id: str
    tool_call_id: str
    response: str
    suggestion_id: Optional[str] = None


class InferTypeRequest(BaseModel):
    property_name: str


class SuggestConstraintsRequest(BaseModel):
    property_name: str
    data_type: str


class RejectSuggestionRequest(BaseModel):
    reason: Optional[str] = None


class AISuggestionResponse(BaseModel):
    suggestion_id: str
    ontology_id: str
    target_type: str
    target_id: Optional[str] = None
    suggestion_category: str
    content: Dict[str, Any] = Field(default_factory=dict)
    source: str
    confidence: float = 0.0
    status: str = "pending"
    rejection_reason: Optional[str] = None
    session_id: Optional[str] = None
    created_at: str
    resolved_at: Optional[str] = None


class AIAssistantSessionResponse(BaseModel):
    session_id: str
    ontology_id: str
    user_id: str
    context_type: str
    context_id: Optional[str] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    hitl_pending: bool = False
    status: str = "active"
    created_at: str
    updated_at: str


class HealthResponse(BaseModel):
    status: str
    llm_available: bool
    rule_engine_available: bool
    ag_ui_protocol: str
    message: Optional[str] = None
