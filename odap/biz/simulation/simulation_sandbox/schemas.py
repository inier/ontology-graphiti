from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class SimulationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MetricChange(BaseModel):
    metric_name: str
    before: Any = None
    after: Any = None
    delta: Optional[float] = None
    unit: str = ""


class WhatIfScenario(BaseModel):
    scenario_id: str = ""
    name: str = ""
    description: str = ""
    action_type_id: str
    target_object_id: str
    target_object_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    variant_parameters: List[Dict[str, Any]] = Field(default_factory=list)
    ontology_id: str = ""
    workspace_id: str = ""


class WhatIfResult(BaseModel):
    scenario_id: str
    status: SimulationStatus
    baseline_metrics: Dict[str, Any] = Field(default_factory=dict)
    projected_metrics: List[Dict[str, Any]] = Field(default_factory=list)
    metric_changes: List[MetricChange] = Field(default_factory=list)
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)
    recommendation: str = ""
    confidence: float = 0.0
    error: Optional[str] = None
    simulated_writes: List[Dict[str, Any]] = Field(default_factory=list)
    adoption_available: bool = True


class WhatIfComparison(BaseModel):
    scenarios: List[WhatIfResult] = Field(default_factory=list)
    best_scenario_id: Optional[str] = None
    summary: str = ""
