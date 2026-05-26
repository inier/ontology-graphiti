from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid


class DeductionStatus(str, Enum):
    DRAFT = "draft"
    CONFIGURING = "configuring"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConditionType(str, Enum):
    RULE_BASED = "rule_based"
    CONSTRAINT_BASED = "constraint_based"
    CUSTOM = "custom"


class ChainStatus(str, Enum):
    PENDING = "pending"
    SIMULATING = "simulating"
    COMPLETED = "completed"
    FAILED = "failed"


class SimulationCondition(BaseModel):
    condition_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    condition_type: ConditionType = ConditionType.CUSTOM
    description: str = ""
    source_rule_id: Optional[str] = None
    source_constraint_id: Optional[str] = None
    expression: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    value: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: List[Any] = Field(default_factory=list)
    is_active: bool = True


class ChainStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_order: int = 0
    action_type_id: str = ""
    target_object_id: str = ""
    target_object_type: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    conditions: List[SimulationCondition] = Field(default_factory=list)
    description: str = ""


class ExecutionChain(BaseModel):
    chain_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    steps: List[ChainStep] = Field(default_factory=list)
    conditions: List[SimulationCondition] = Field(default_factory=list)
    status: ChainStatus = ChainStatus.PENDING
    estimated_duration: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class MetricImpact(BaseModel):
    metric_name: str
    before: Any = None
    after: Any = None
    delta: Optional[float] = None
    unit: str = ""
    confidence: float = 0.0


class RuleViolation(BaseModel):
    rule_id: str
    rule_type: str
    description: str
    severity: str = "warning"
    violated_condition: str = ""


class ChainResult(BaseModel):
    chain_id: str
    status: ChainStatus = ChainStatus.COMPLETED
    metric_impacts: List[MetricImpact] = Field(default_factory=list)
    risk_level: str = "low"
    risk_score: float = 0.0
    rule_violations: List[RuleViolation] = Field(default_factory=list)
    recommendation: str = ""
    confidence: float = 0.0
    projected_state: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class DeductionScenario(BaseModel):
    scenario_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    source_recommendation_id: Optional[str] = None
    source_analysis_id: Optional[str] = None
    target_object_id: str = ""
    target_object_type: str = ""
    baseline_metrics: Dict[str, Any] = Field(default_factory=dict)
    available_conditions: List[SimulationCondition] = Field(default_factory=list)
    chains: List[ExecutionChain] = Field(default_factory=list)
    results: List[ChainResult] = Field(default_factory=list)
    status: DeductionStatus = DeductionStatus.DRAFT
    best_chain_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
