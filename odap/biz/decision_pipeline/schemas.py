from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class PipelineStageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AnalysisInput(BaseModel):
    query: str
    context: Dict[str, Any] = {}
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    agent_id: Optional[str] = None


class AnalysisResult(BaseModel):
    summary: str = ""
    entities: List[Dict[str, Any]] = []
    relations: List[Dict[str, Any]] = []
    patterns: List[Dict[str, Any]] = []
    risks: List[Dict[str, Any]] = []
    confidence: float = 0.0
    raw_context: str = ""


class DecisionOption(BaseModel):
    option_id: str = ""
    name: str = ""
    description: str = ""
    action_type_id: str = ""
    target_object_id: str = ""
    target_object_type: str = ""
    parameters: Dict[str, Any] = {}
    risk_level: str = "low"
    expected_outcome: str = ""
    priority: int = 0


class DecisionResult(BaseModel):
    decision_id: str = ""
    recommended_option: Optional[DecisionOption] = None
    alternative_options: List[DecisionOption] = []
    opa_approved: bool = False
    opa_decision: Optional[Dict[str, Any]] = None
    reasoning: str = ""
    confidence: float = 0.0


class ActionCommand(BaseModel):
    action_type_id: str
    target_object_id: str
    target_object_type: str
    parameters: Dict[str, Any] = {}
    requested_by: str = "decision_pipeline"
    reason: str = ""
    agent_id: Optional[str] = None
    confirmation_required: bool = False


class PipelineResult(BaseModel):
    pipeline_id: str = ""
    analysis: Optional[AnalysisResult] = None
    decision: Optional[DecisionResult] = None
    action_record: Optional[Dict[str, Any]] = None
    feedback: Optional[Dict[str, Any]] = None
    stages: Dict[str, PipelineStageStatus] = {}
    error: Optional[str] = None
