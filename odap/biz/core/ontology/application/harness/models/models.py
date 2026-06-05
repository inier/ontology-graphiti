from .types import HarnessStage, StageStatus, HITLRiskLevel, AgentRole
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class StageResult(BaseModel):
    stage: HarnessStage
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    duration_ms: int = 0


class HITLConfirmation(BaseModel):
    confirmation_id: str = Field(default_factory=lambda: f"hitl-{uuid.uuid4().hex[:8]}")
    stage: HarnessStage
    risk_level: HITLRiskLevel = HITLRiskLevel.MEDIUM
    title: str = ""
    description: str = ""
    impact_analysis: str = ""
    affected_objects: List[str] = Field(default_factory=list)
    suggested_action: str = ""
    is_resolved: bool = False
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AgentTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    agent_type: str = ""
    stage: HarnessStage
    description: str = ""
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    status: StageStatus = StageStatus.PENDING
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AgentMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:8]}")
    from_agent: str = ""
    to_agent: str = ""
    message_type: str = ""
    content: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SubTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    agent_role: AgentRole = AgentRole.PLANNING
    description: str = ""
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    status: StageStatus = StageStatus.PENDING
    error: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


class HarnessSession(BaseModel):
    session_id: str = Field(default_factory=lambda: f"harness-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    current_stage: HarnessStage = HarnessStage.DATA_SELECTION
    stage_results: List[StageResult] = Field(default_factory=list)
    hitl_confirmations: List[HITLConfirmation] = Field(default_factory=list)
    agent_tasks: List[AgentTask] = Field(default_factory=list)
    context_memory: Dict[str, Any] = Field(default_factory=dict)
    scenario_id: Optional[str] = None
    workspace_id: Optional[str] = None
    status: StageStatus = StageStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    requirement: str = ""
    sub_tasks: List[SubTask] = Field(default_factory=list)
    messages: List[AgentMessage] = Field(default_factory=list)
    planning_output: Dict[str, Any] = Field(default_factory=dict)
    ontology_output: Dict[str, Any] = Field(default_factory=dict)
    execution_output: Dict[str, Any] = Field(default_factory=dict)


class BlueprintNode(BaseModel):
    node_id: str = Field(default_factory=lambda: f"bp-node-{uuid.uuid4().hex[:8]}")
    node_type: str = ""
    label: str = ""
    stage: HarnessStage
    config: Dict[str, Any] = Field(default_factory=dict)
    position_x: int = 0
    position_y: int = 0


class BlueprintEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: f"bp-edge-{uuid.uuid4().hex[:8]}")
    source_node_id: str = ""
    target_node_id: str = ""
    label: str = ""
    data_mapping: Dict[str, str] = Field(default_factory=dict)


class OntologyBlueprint(BaseModel):
    blueprint_id: str = Field(default_factory=lambda: f"bp-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    nodes: List[BlueprintNode] = Field(default_factory=list)
    edges: List[BlueprintEdge] = Field(default_factory=list)
    session_id: Optional[str] = None
    version: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class RequirementAnalysis(BaseModel):
    business_objects: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    processing_needs: List[Dict[str, Any]] = Field(default_factory=list)
    risks: List[Dict[str, Any]] = Field(default_factory=list)
    missing_info: List[str] = Field(default_factory=list)


class OntologySuggestion(BaseModel):
    object_types: List[Dict[str, Any]] = Field(default_factory=list)
    link_types: List[Dict[str, Any]] = Field(default_factory=list)
    functions: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    constraints: List[Dict[str, Any]] = Field(default_factory=list)
